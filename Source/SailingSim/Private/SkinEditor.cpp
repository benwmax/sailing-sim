#include "SkinEditor.h"
#include "SailingSim.h"
#include "BoatLivery.h"
#include "SailSave.h"

namespace SkinEditorLocal
{
	const TCHAR* const PartNames[int32(FSkinEditor::EPart::Count)] = { TEXT("Hull"), TEXT("Deck"), TEXT("Non-skid"), TEXT("Bottom paint"),
		TEXT("Boot stripe"), TEXT("Cove stripe"), TEXT("Trim"), TEXT("Mast and boom") };

	// The rope colourways as the player reads them, and each one's main colour (sRGB) for its chip, in T_RopeColourways'
	// column order (FBoatSkin::RopeColourwayId).
	struct FRope { const TCHAR* Name; uint32 Chip; };
	const FRope Ropes[] = { { TEXT("White, red fleck"), 0xF0EEE8 }, { TEXT("Red, white fleck"), 0xB3201B }, { TEXT("Green, white fleck"), 0x1F7A3D },
		{ TEXT("White, green fleck"), 0xF0EEE8 }, { TEXT("White, blue fleck"), 0xF0EEE8 }, { TEXT("Blue and white"), 0x2F5FA8 },
		{ TEXT("Black, white fleck"), 0x1B1D20 }, { TEXT("Solid blue"), 0x1F4E9C }, { TEXT("White, red spiral"), 0xF0EEE8 },
		{ TEXT("Grey, red fleck"), 0x8A9096 }, { TEXT("Yellow, black fleck"), 0xE3B321 } };

	// What an edit changes, for folding a dragged value's steps into one (0 is never folded).
	constexpr int32 EditPart = 100;    // + the part

	// (case counts: "my navy" renamed "My Navy" is a change)
	bool SameText(const FBoatSkin& A, const FBoatSkin& B) { return A.ToJson().Equals(B.ToJson(), ESearchCase::CaseSensitive); }
}

const TCHAR* FSkinEditor::PartName(EPart Part)
{
	return SkinEditorLocal::PartNames[FMath::Clamp(int32(Part), 0, int32(EPart::Count) - 1)];
}

FString FSkinEditor::RopeName(int32 Column)
{
	return Column >= 0 && Column < int32(UE_ARRAY_COUNT(SkinEditorLocal::Ropes)) ? FString(SkinEditorLocal::Ropes[Column].Name) : FString(TEXT("The boat's own"));
}

FLinearColor FSkinEditor::RopeChip(int32 Column)
{
	if (Column < 0 || Column >= int32(UE_ARRAY_COUNT(SkinEditorLocal::Ropes))) return FLinearColor(0.2f, 0.2f, 0.2f);
	const uint32 C = SkinEditorLocal::Ropes[Column].Chip;
	return FLinearColor(FColor(uint8((C >> 16) & 255), uint8((C >> 8) & 255), uint8(C & 255)));
}

void FSkinEditor::Open(int32 InBoatType)
{
	FBoatSkin Worn;
	const FString Chosen = SailSaveStore::BoatSkin(FSailSave::BoatId(InBoatType));
	const bool bWorn = !Chosen.IsEmpty() && BoatSkinStore::Find(InBoatType, Chosen, Worn);
	OpenWith(InBoatType, bWorn ? &Worn : nullptr);
}

void FSkinEditor::OpenWith(int32 InBoatType, const FBoatSkin* Worn)
{
	BoatType = InBoatType;
	Load(Worn);
	WornId = Baseline.Id;
	ResetHistory();
}

void FSkinEditor::ResetHistory()
{
	// (where the draft stands is where undo stops)
	History.Reset();
	Bases.Reset();
	History.Add(Draft);
	Bases.Add(Baseline);
	At = 0;
	LastEdit = 0;
}

bool FSkinEditor::IsDirty() const
{
	// (asked several times a frame by the screen: the answer is kept until the draft or what it is compared to changes)
	if (DirtyAt != Revision || !bDirtyKnown)
	{
		bDirtyCached = !SkinEditorLocal::SameText(Draft, Baseline);
		DirtyAt = Revision;
		bDirtyKnown = true;
	}
	return bDirtyCached;
}

void FSkinEditor::Record(int32 Edit)
{
	++Revision;
	// Anything after where we stand is gone (a change after an undo); a dragged value replaces its own last step.
	// Each step keeps what the draft was compared to as well, so undoing a load brings back the skin loaded before it
	// (and Use then writes that skin's file, not the later one's).
	History.SetNum(FMath::Min(At + 1, History.Num()));
	Bases.SetNum(History.Num());
	if (Edit != 0 && Edit == LastEdit && History.Num() > 1)
	{
		History.Last() = Draft;
		Bases.Last() = Baseline;
	}
	else
	{
		History.Add(Draft);
		Bases.Add(Baseline);
		if (History.Num() > MaxUndo + 1)
		{
			History.RemoveAt(0);
			Bases.RemoveAt(0);
		}
	}
	At = History.Num() - 1;
	LastEdit = Edit;
}

void FSkinEditor::Load(const FBoatSkin* Skin)
{
	Draft = Skin ? *Skin : FBoatSkin();
	if (!Skin)
	{
		Draft.Id.Reset();
		Draft.Name.Reset();
	}
	Draft.BoatId = FSailSave::BoatId(BoatType);
	Baseline = Draft;
	Record(0);
}

TOptional<FLinearColor>& FSkinEditor::PartRef(EPart Part)
{
	FBoatSkin::FPaint& P = Draft.Paint;
	switch (Part)
	{
	case EPart::Hull: return P.Hull;
	case EPart::Deck: return P.Deck;
	case EPart::NonSkid: return P.NonSkid;
	case EPart::Bottom: return P.Bottom;
	case EPart::Boot: return P.Boot;
	case EPart::Cove: return P.Cove;
	case EPart::Trim: return P.Trim;
	default: return P.Spars;
	}
}

TOptional<FLinearColor> FSkinEditor::PartColour(EPart Part) const
{
	return const_cast<FSkinEditor*>(this)->PartRef(Part);
}

bool FSkinEditor::IsPartOff(EPart Part) const
{
	if (Part == EPart::Boot) return Draft.Paint.bBoot.IsSet() && !Draft.Paint.bBoot.GetValue();
	if (Part == EPart::Spars) return Draft.Paint.bSparsPainted.IsSet() && !Draft.Paint.bSparsPainted.GetValue();
	if (Part == EPart::Cove) return Draft.Paint.bCove.IsSet() && !Draft.Paint.bCove.GetValue();
	if (Part == EPart::Trim) return Draft.Paint.bTrim.IsSet() && !Draft.Paint.bTrim.GetValue();
	return false;
}

void FSkinEditor::SetPartColour(EPart Part, const FLinearColor& Colour, bool bDragged)
{
	PartRef(Part) = FLinearColor(FMath::Clamp(Colour.R, 0.f, 1.f), FMath::Clamp(Colour.G, 0.f, 1.f), FMath::Clamp(Colour.B, 0.f, 1.f));
	if (Part == EPart::Boot) Draft.Paint.bBoot = true;
	if (Part == EPart::Spars) Draft.Paint.bSparsPainted = true;
	if (Part == EPart::Cove) Draft.Paint.bCove = true;
	if (Part == EPart::Trim) Draft.Paint.bTrim = true;
	Record(bDragged ? SkinEditorLocal::EditPart + int32(Part) : 0);
}

void FSkinEditor::ClearPart(EPart Part)
{
	PartRef(Part).Reset();
	if (Part == EPart::Boot) Draft.Paint.bBoot.Reset();
	if (Part == EPart::Spars) Draft.Paint.bSparsPainted.Reset();
	if (Part == EPart::Cove) Draft.Paint.bCove.Reset();
	if (Part == EPart::Trim) Draft.Paint.bTrim.Reset();
	Record(0);
}

void FSkinEditor::SetPartOff(EPart Part)
{
	if (!PartCanBeOff(Part)) { ClearPart(Part); return; }
	PartRef(Part).Reset();
	if (Part == EPart::Boot) Draft.Paint.bBoot = false;
	if (Part == EPart::Spars) Draft.Paint.bSparsPainted = false;
	if (Part == EPart::Cove) Draft.Paint.bCove = false;
	if (Part == EPart::Trim) Draft.Paint.bTrim = false;
	Record(0);
}

void FSkinEditor::SetWearLevel(int32 Level)
{
	Draft.Wear.Level = Level < 0 ? -1 : FMath::Min(Level, FBoatSkin::NumWearLevels - 1);
	Draft.Wear.AgeYears.Reset();
	Draft.Wear.Care.Reset();
	Record(0);
}

void FSkinEditor::SetSailCloth(const TOptional<FLinearColor>& Cloth)
{
	Draft.Sails.Cloth = Cloth;
	Record(0);
}

void FSkinEditor::SetSailNumber(const TOptional<FString>& Number)
{
	if (Number.IsSet())
	{
		FString Digits;
		for (const TCHAR Ch : Number.GetValue()) if (Ch >= TEXT('0') && Ch <= TEXT('9') && Digits.Len() < FBoatSkin::MaxSailDigits) Digits.AppendChar(Ch);
		Draft.Sails.Number = Digits;
	}
	else Draft.Sails.Number.Reset();
	Record(0);
}

void FSkinEditor::SetClassMark(const TOptional<bool>& bMark)
{
	Draft.Sails.bClassMark = bMark;
	Record(0);
}

void FSkinEditor::SetLine(FBoatSkin::ELine Line, int32 Column)
{
	const int32 I = int32(Line);
	if (I < 0 || I >= int32(FBoatSkin::ELine::Count)) return;
	Draft.Lines.Column[I] = Column >= 0 && Column < FBoatSkin::NumRopeColourways() ? Column : -1;
	Record(0);
}

void FSkinEditor::SetName(const FString& Name)
{
	Draft.Name = FBoatSkin::CleanName(Name);
	Record(0);
}

void FSkinEditor::Surprise(FRandomStream& Random)
{
	const TArray<FBoatSkin> BuiltIn = BoatSkinStore::BuiltIn(BoatType);
	if (BuiltIn.Num() > 0) Draft.Paint = BuiltIn[Random.RandRange(0, BuiltIn.Num() - 1)].Paint;
	Draft.Wear = FBoatSkin::FWear();
	Draft.Wear.Level = Random.RandRange(0, 3);
	// The sheets: any colourway for the mainsheet and the control lines; the jib sheets keep port red and starboard green
	// (columns 1 and 2) two times in three, as most boats rig them.
	const int32 Ways = FBoatSkin::NumRopeColourways();
	Draft.Lines.Column[int32(FBoatSkin::ELine::Mainsheet)] = Random.RandRange(0, Ways - 1);
	Draft.Lines.Column[int32(FBoatSkin::ELine::Control)] = Random.RandRange(0, Ways - 1);
	const bool bConvention = Random.RandRange(0, 2) != 0;
	Draft.Lines.Column[int32(FBoatSkin::ELine::JibPort)] = bConvention ? 1 : Random.RandRange(0, Ways - 1);
	Draft.Lines.Column[int32(FBoatSkin::ELine::JibStarboard)] = bConvention ? 2 : Draft.Lines.Column[int32(FBoatSkin::ELine::JibPort)];
	Record(0);
}

bool FSkinEditor::Undo()
{
	if (!CanUndo()) return false;
	Draft = History[--At];
	Baseline = Bases[At];
	LastEdit = 0;
	++Revision;
	return true;
}

bool FSkinEditor::Redo()
{
	if (!CanRedo()) return false;
	Draft = History[++At];
	Baseline = Bases[At];
	LastEdit = 0;
	++Revision;
	return true;
}

FSkinEditor::ESavePlan FSkinEditor::SavePlan() const
{
	if (Draft.Paint.IsEmpty() && Draft.Wear.IsEmpty() && Draft.Sails.IsEmpty() && Draft.Lines.IsEmpty()) return ESavePlan::ClassLook;
	if (!IsDirty() && !Baseline.Id.IsEmpty()) return ESavePlan::Existing;
	if (!Baseline.Id.IsEmpty() && !Baseline.bBuiltIn) return ESavePlan::Overwrite;
	return ESavePlan::NewFile;
}

FString FSkinEditor::NewName() const
{
	// A name the player typed is theirs; else "My navy" from the built-in it started as, or "My look".
	if (!Draft.Name.IsEmpty() && Draft.Name != Baseline.Name) return Draft.Name;
	if (Baseline.Name.IsEmpty()) return TEXT("My look");
	if (!Baseline.bBuiltIn) return Baseline.Name;
	return TEXT("My ") + Baseline.Name.Left(1).ToLower() + Baseline.Name.RightChop(1);
}

bool FSkinEditor::WriteAs(const FString& Id, const FString& Name)
{
	FBoatSkin Out = Draft;
	Out.Id = Id;
	Out.Name = Name;
	Out.bBuiltIn = false;
	Out.BoatId = FSailSave::BoatId(BoatType);
	if (!BoatSkinStore::Save(Out)) return false;
	Draft = Out;
	Baseline = Out;
	bDirtyKnown = false;
	// (the step undo stands on is now the saved skin: undoing past it and using that writes this file again)
	if (History.IsValidIndex(At)) { History[At] = Draft; Bases[At] = Baseline; }
	return true;
}

bool FSkinEditor::Use()
{
	const FString Boat = FSailSave::BoatId(BoatType);
	switch (SavePlan())
	{
	case ESavePlan::ClassLook:
		SailSaveStore::SetBoatSkin(Boat, FString());
		Draft.Id.Reset();
		Draft.Name.Reset();
		Baseline = Draft;
		bDirtyKnown = false;
		break;
	case ESavePlan::Existing:
		SailSaveStore::SetBoatSkin(Boat, Baseline.Id);
		break;
	case ESavePlan::Overwrite:
	{
		const FString Id = Baseline.Id, Name = Draft.Name.IsEmpty() ? Baseline.Name : Draft.Name;   // (copies: WriteAs replaces Baseline)
		if (!WriteAs(Id, Name)) return false;
		SailSaveStore::SetBoatSkin(Boat, Id);
		break;
	}
	case ESavePlan::NewFile:
		return SaveAsNew();
	}
	SailSaveStore::Commit();
	WornId = Baseline.Id;
	++Revision;
	return true;
}

bool FSkinEditor::SaveAsNew()
{
	const FString Name = NewName();
	const FString Id = BoatSkinStore::FreeId(Name);
	// A second "My navy" is "My navy 2", as its id is.
	const FString Base = FBoatSkin::CleanId(Name);
	const FString Shown = Id.Len() > Base.Len() + 1 && Id.StartsWith(Base) ? FBoatSkin::CleanName(Name.Left(FBoatSkin::MaxNameChars - 4) + TEXT(" ") + Id.RightChop(Base.Len() + 1)) : Name;
	if (!WriteAs(Id, Shown)) return false;
	SailSaveStore::SetBoatSkin(FSailSave::BoatId(BoatType), Id);
	SailSaveStore::Commit();
	WornId = Baseline.Id;
	++Revision;
	return true;
}

bool FSkinEditor::DeleteLoaded()
{
	if (Baseline.Id.IsEmpty() || Baseline.bBuiltIn) return false;
	const FString Id = Baseline.Id;
	if (!BoatSkinStore::Delete(Id)) return false;
	const FString Boat = FSailSave::BoatId(BoatType);
	if (SailSaveStore::BoatSkin(Boat) == Id)
	{
		SailSaveStore::SetBoatSkin(Boat, FString());
		SailSaveStore::Commit();
	}
	if (WornId == Id) WornId.Reset();
	Load(nullptr);
	// (no undo back to a skin whose file is gone)
	ResetHistory();
	return true;
}
