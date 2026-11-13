#include "BoatSkin.h"
#include "SailingSim.h"
#include "BenchRunner.h"
#include "BoatLivery.h"
#include "BoatModel.h"
#include "SailSave.h"
#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace BoatSkinLocal
{
	const TCHAR* const FormatId = TEXT("ready-about-skin");
	const TCHAR* const BuiltInPrefix = TEXT("builtin-");
	const TCHAR* const FileSuffix = TEXT(".skin.json");

	// The texture loop's ladder (docs/texture-loop): Age in years, Care 0..1, and the share of the class's club wear
	// range the livery's four channels take (SetLiveryWear). Level 2 is the club boat every class already is unset.
	struct FWearLevel { const TCHAR* Id; const TCHAR* Name; float Age, Care, Share; };
	const FWearLevel WearLevels[FBoatSkin::NumWearLevels] = {
		{ TEXT("new"), TEXT("New"), 0.f, 1.f, 0.f },
		{ TEXT("months"), TEXT("A season in"), 0.3f, 0.9f, 0.15f },
		{ TEXT("club"), TEXT("Club boat"), 6.f, 0.5f, 0.5f },
		{ TEXT("classic"), TEXT("Decades, well kept"), 30.f, 0.9f, 0.45f },
		{ TEXT("neglected"), TEXT("Neglected"), 20.f, 0.1f, 1.f },
	};
	constexpr int32 ClubLevel = 2;

	// T_RopeColourways' columns, in Inputs/rope/colourways.json order (SailingSim.Skin.RopeColourways holds the two in step).
	const TCHAR* const RopeIds[] = { TEXT("white_red_fleck"), TEXT("red_white_fleck"), TEXT("green_white_fleck"), TEXT("white_green_fleck"),
		TEXT("white_blue_fleck"), TEXT("blue_white_mix"), TEXT("black_white_fleck"), TEXT("blue_solid"), TEXT("white_spiral_red"),
		TEXT("grey_red_fleck"), TEXT("yellow_black_fleck") };
	const TCHAR* const LineIds[int32(FBoatSkin::ELine::Count)] = { TEXT("mainsheet"), TEXT("jibPort"), TEXT("jibStarboard"), TEXT("control") };
	// The rope looks the rig lines carry (RopeLook in BoatModelVisuals.cpp): mainsheet 0, port jib sheet 1, starboard 2, vang and control lines 5.
	const uint8 LineLooks[int32(FBoatSkin::ELine::Count)] = { 0, 1, 2, 5 };

	TSharedPtr<FJsonObject> Child(const FJsonObject& O, const TCHAR* Key)
	{
		const TSharedPtr<FJsonObject>* C = nullptr;
		return O.TryGetObjectField(Key, C) && C ? *C : TSharedPtr<FJsonObject>();
	}

	void ReadColour(const FJsonObject& O, const TCHAR* Key, TOptional<FLinearColor>& Out)
	{
		FString Text;
		FLinearColor C;
		if (O.TryGetStringField(Key, Text) && FBoatSkin::ParseHex(Text, C)) Out = C;
	}

	void WriteColour(FJsonObject& O, const TCHAR* Key, const TOptional<FLinearColor>& In)
	{
		if (In.IsSet()) O.SetStringField(Key, FBoatSkin::ToHex(In.GetValue()));
	}

	int32 HexDigit(TCHAR Ch)
	{
		return Ch >= TEXT('0') && Ch <= TEXT('9') ? int32(Ch - TEXT('0'))
			: Ch >= TEXT('a') && Ch <= TEXT('f') ? int32(Ch - TEXT('a')) + 10
			: Ch >= TEXT('A') && Ch <= TEXT('F') ? int32(Ch - TEXT('A')) + 10 : -1;
	}

	FString FileOf(const FString& Id) { return BoatSkinStore::Dir() / (Id + FileSuffix); }

	/** A built-in: a catalogue scheme's paint (and optionally a wear level) under a name. */
	FBoatSkin MakeBuiltIn(int32 BoatType, const TCHAR* Slug, const TCHAR* Name, int32 Scheme, int32 WearLevel)
	{
		FBoatSkin S;
		S.bBuiltIn = true;
		S.BoatId = FSailSave::BoatId(BoatType);
		S.Id = FString::Printf(TEXT("%s%s-%s"), BuiltInPrefix, *S.BoatId.ToLower(), Slug);
		S.Name = Name;
		const FBoatLivery L = LiveryForScheme(BoatType, Scheme);
		S.Paint.Hull = L.Hull; S.Paint.Deck = L.Deck; S.Paint.NonSkid = L.NonSkid; S.Paint.Bottom = L.Bottom;
		S.Paint.bBoot = L.bBoot;
		if (L.bBoot) S.Paint.Boot = L.Boot;
		// (said either way: a scheme without a cove stripe or teak takes them off a class whose own look has them)
		S.Paint.bCove = L.bCove;
		if (L.bCove) S.Paint.Cove = L.Cove;
		S.Paint.bTrim = L.bTeak;
		if (L.bTeak) S.Paint.Trim = L.Teak;
		S.Wear.Level = WearLevel;
		return S;
	}
}

// ---------------------------------------------------------------- ids and text

const TCHAR* FBoatSkin::WearLevelId(int32 Level)
{
	return BoatSkinLocal::WearLevels[FMath::Clamp(Level, 0, NumWearLevels - 1)].Id;
}

int32 FBoatSkin::WearLevelIndex(const FString& InId)
{
	for (int32 I = 0; I < NumWearLevels; ++I) if (InId == BoatSkinLocal::WearLevels[I].Id) return I;
	return -1;
}

FText FBoatSkin::WearLevelName(int32 Level)
{
	return FText::FromString(BoatSkinLocal::WearLevels[FMath::Clamp(Level, 0, NumWearLevels - 1)].Name);
}

const TCHAR* FBoatSkin::LineId(ELine Line)
{
	return BoatSkinLocal::LineIds[FMath::Clamp(int32(Line), 0, int32(ELine::Count) - 1)];
}

int32 FBoatSkin::NumRopeColourways() { return int32(UE_ARRAY_COUNT(BoatSkinLocal::RopeIds)); }

const TCHAR* FBoatSkin::RopeColourwayId(int32 Column)
{
	return Column >= 0 && Column < NumRopeColourways() ? BoatSkinLocal::RopeIds[Column] : TEXT("");
}

int32 FBoatSkin::RopeColourwayIndex(const FString& InId)
{
	for (int32 I = 0; I < NumRopeColourways(); ++I) if (InId == BoatSkinLocal::RopeIds[I]) return I;
	return -1;
}

bool FBoatSkin::ParseHex(const FString& Text, FLinearColor& Out)
{
	if (Text.Len() != 7 || Text[0] != TEXT('#')) return false;
	int32 V[6];
	for (int32 I = 0; I < 6; ++I)
	{
		V[I] = BoatSkinLocal::HexDigit(Text[I + 1]);
		if (V[I] < 0) return false;
	}
	Out = FLinearColor::FromSRGBColor(FColor(uint8(V[0] * 16 + V[1]), uint8(V[2] * 16 + V[3]), uint8(V[4] * 16 + V[5]), 255));
	return true;
}

FString FBoatSkin::ToHex(const FLinearColor& Linear)
{
	const FColor C = Linear.GetClamped().ToFColorSRGB();
	return FString::Printf(TEXT("#%02X%02X%02X"), int32(C.R), int32(C.G), int32(C.B));
}

FString FBoatSkin::CleanId(const FString& In)
{
	FString Out;
	for (TCHAR Ch : In.ToLower())
	{
		if (Out.Len() >= MaxIdChars) break;
		if ((Ch >= TEXT('a') && Ch <= TEXT('z')) || (Ch >= TEXT('0') && Ch <= TEXT('9'))) Out.AppendChar(Ch);
		else if (Out.Len() > 0 && !Out.EndsWith(TEXT("-"))) Out.AppendChar(TEXT('-')); // anything else parts two words, once
	}
	while (Out.EndsWith(TEXT("-"))) Out.LeftChopInline(1);
	return Out;
}

FString FBoatSkin::CleanName(const FString& In)
{
	FString Out;
	for (TCHAR Ch : In)
	{
		if (Out.Len() >= MaxNameChars) break;
		const bool bLetter = (Ch >= TEXT('a') && Ch <= TEXT('z')) || (Ch >= TEXT('A') && Ch <= TEXT('Z')) || (Ch >= TEXT('0') && Ch <= TEXT('9'));
		const bool bMark = Ch == TEXT(' ') || Ch == TEXT('.') || Ch == TEXT(',') || Ch == TEXT('\'') || Ch == TEXT('&') || Ch == TEXT('-') || Ch == TEXT('/');
		if (bLetter || (bMark && Out.Len() > 0)) Out.AppendChar(Ch);
	}
	Out.TrimEndInline();
	return Out;
}

// ---------------------------------------------------------------- the file

FBoatSkin::EResult FBoatSkin::FromJson(const FString& Text, FBoatSkin& Out, FString* OutMessage)
{
	using namespace BoatSkinLocal;
	auto Say = [OutMessage](const FString& M) { if (OutMessage) *OutMessage = M; };
	Out = FBoatSkin();
	if (Text.Len() > MaxFileBytes)
	{
		Say(FString::Printf(TEXT("larger than %d KB"), MaxFileBytes / 1024));
		return EResult::Refused;
	}
	TSharedPtr<FJsonObject> Root;
	if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid())
	{
		Say(TEXT("not JSON"));
		return EResult::Invalid;
	}
	FString Format;
	if (!Root->TryGetStringField(TEXT("format"), Format) || Format != FormatId)
	{
		Say(TEXT("not a skin file"));
		return EResult::Invalid;
	}
	int32 FileVersion = -1;
	if (!Root->TryGetNumberField(TEXT("version"), FileVersion) || FileVersion < 1)
	{
		Say(TEXT("no version number"));
		return EResult::Invalid;
	}
	if (FileVersion > CurrentVersion)
	{
		Say(FString::Printf(TEXT("version %d is newer than this game's %d"), FileVersion, CurrentVersion));
		return EResult::Refused;
	}
	FString Text1;
	if (Root->TryGetStringField(TEXT("id"), Text1)) Out.Id = CleanId(Text1);
	if (Root->TryGetStringField(TEXT("name"), Text1)) Out.Name = CleanName(Text1);
	if (Root->TryGetStringField(TEXT("boat"), Text1) && FSailSave::BoatIndex(Text1) >= 0) Out.BoatId = Text1;
	// A file never makes a built-in: that id space is the game's.
	if (Out.Id.StartsWith(BuiltInPrefix)) Out.Id = CleanId(TEXT("copy-") + Out.Id.RightChop(FCString::Strlen(BuiltInPrefix)));
	if (Out.Name.IsEmpty()) Out.Name = TEXT("Skin");

	if (const TSharedPtr<FJsonObject> P = Child(*Root, TEXT("paint")))
	{
		ReadColour(*P, TEXT("hull"), Out.Paint.Hull);
		ReadColour(*P, TEXT("deck"), Out.Paint.Deck);
		ReadColour(*P, TEXT("nonSkid"), Out.Paint.NonSkid);
		ReadColour(*P, TEXT("bottom"), Out.Paint.Bottom);
		FString Boot, Spars, Cove, Trim;
		if (P->TryGetStringField(TEXT("cove"), Cove))
		{
			if (Cove == TEXT("none")) Out.Paint.bCove = false;
			else { ReadColour(*P, TEXT("cove"), Out.Paint.Cove); if (Out.Paint.Cove.IsSet()) Out.Paint.bCove = true; }
		}
		if (P->TryGetStringField(TEXT("trim"), Trim))
		{
			if (Trim == TEXT("none")) Out.Paint.bTrim = false;
			else { ReadColour(*P, TEXT("trim"), Out.Paint.Trim); if (Out.Paint.Trim.IsSet()) Out.Paint.bTrim = true; }
		}
		if (P->TryGetStringField(TEXT("boot"), Boot))
		{
			if (Boot == TEXT("none")) Out.Paint.bBoot = false;
			else { ReadColour(*P, TEXT("boot"), Out.Paint.Boot); if (Out.Paint.Boot.IsSet()) Out.Paint.bBoot = true; }
		}
		if (P->TryGetStringField(TEXT("spars"), Spars))
		{
			if (Spars == TEXT("bare")) Out.Paint.bSparsPainted = false;
			else { ReadColour(*P, TEXT("spars"), Out.Paint.Spars); if (Out.Paint.Spars.IsSet()) Out.Paint.bSparsPainted = true; }
		}
	}
	if (const TSharedPtr<FJsonObject> W = Child(*Root, TEXT("wear")))
	{
		FString Level;
		if (W->TryGetStringField(TEXT("level"), Level)) Out.Wear.Level = WearLevelIndex(Level);
		double Age = 0.0, CareIn = 0.0;
		if (W->TryGetNumberField(TEXT("ageYears"), Age) && FMath::IsFinite(Age))
		{
			Out.Wear.AgeYears = float(FMath::Clamp(Age, 0.0, 60.0));
			Out.Wear.Care = W->TryGetNumberField(TEXT("care"), CareIn) && FMath::IsFinite(CareIn) ? float(FMath::Clamp(CareIn, 0.0, 1.0)) : 0.5f;
		}
	}
	if (const TSharedPtr<FJsonObject> S = Child(*Root, TEXT("sails")))
	{
		ReadColour(*S, TEXT("cloth"), Out.Sails.Cloth);
		FString Number;
		if (S->TryGetStringField(TEXT("number"), Number))
		{
			FString Digits;
			for (TCHAR Ch : Number) if (Ch >= TEXT('0') && Ch <= TEXT('9') && Digits.Len() < MaxSailDigits) Digits.AppendChar(Ch);
			Out.Sails.Number = Digits;
		}
		// (a real boolean only: TryGetBoolField would read the text "yes")
		if (S->HasTypedField<EJson::Boolean>(TEXT("classMark"))) Out.Sails.bClassMark = S->GetBoolField(TEXT("classMark"));
	}
	if (const TSharedPtr<FJsonObject> L = Child(*Root, TEXT("lines")))
	{
		for (int32 I = 0; I < int32(ELine::Count); ++I)
		{
			FString Way;
			if (L->TryGetStringField(LineIds[I], Way)) Out.Lines.Column[I] = RopeColourwayIndex(Way);
		}
	}
	Say(TEXT("ok"));
	return EResult::Ok;
}

FString FBoatSkin::ToJson() const
{
	using namespace BoatSkinLocal;
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("format"), FormatId);
	Root->SetNumberField(TEXT("version"), CurrentVersion);
	Root->SetStringField(TEXT("id"), Id);
	Root->SetStringField(TEXT("name"), Name);
	if (!BoatId.IsEmpty()) Root->SetStringField(TEXT("boat"), BoatId);
	if (!Paint.IsEmpty())
	{
		TSharedRef<FJsonObject> P = MakeShared<FJsonObject>();
		WriteColour(*P, TEXT("hull"), Paint.Hull);
		WriteColour(*P, TEXT("deck"), Paint.Deck);
		WriteColour(*P, TEXT("nonSkid"), Paint.NonSkid);
		WriteColour(*P, TEXT("bottom"), Paint.Bottom);
		if (Paint.bBoot.IsSet() && !Paint.bBoot.GetValue()) P->SetStringField(TEXT("boot"), TEXT("none"));
		else WriteColour(*P, TEXT("boot"), Paint.Boot);
		if (Paint.bCove.IsSet() && !Paint.bCove.GetValue()) P->SetStringField(TEXT("cove"), TEXT("none"));
		else WriteColour(*P, TEXT("cove"), Paint.Cove);
		if (Paint.bTrim.IsSet() && !Paint.bTrim.GetValue()) P->SetStringField(TEXT("trim"), TEXT("none"));
		else WriteColour(*P, TEXT("trim"), Paint.Trim);
		if (Paint.bSparsPainted.IsSet() && !Paint.bSparsPainted.GetValue()) P->SetStringField(TEXT("spars"), TEXT("bare"));
		else WriteColour(*P, TEXT("spars"), Paint.Spars);
		Root->SetObjectField(TEXT("paint"), P);
	}
	if (!Wear.IsEmpty())
	{
		TSharedRef<FJsonObject> W = MakeShared<FJsonObject>();
		if (Wear.Level >= 0) W->SetStringField(TEXT("level"), WearLevelId(Wear.Level));
		if (Wear.AgeYears.IsSet())
		{
			W->SetNumberField(TEXT("ageYears"), Wear.AgeYears.GetValue());
			W->SetNumberField(TEXT("care"), Wear.Care.Get(0.5f));
		}
		Root->SetObjectField(TEXT("wear"), W);
	}
	if (!Sails.IsEmpty())
	{
		TSharedRef<FJsonObject> S = MakeShared<FJsonObject>();
		WriteColour(*S, TEXT("cloth"), Sails.Cloth);
		if (Sails.Number.IsSet()) S->SetStringField(TEXT("number"), Sails.Number.GetValue());
		if (Sails.bClassMark.IsSet()) S->SetBoolField(TEXT("classMark"), Sails.bClassMark.GetValue());
		Root->SetObjectField(TEXT("sails"), S);
	}
	if (!Lines.IsEmpty())
	{
		TSharedRef<FJsonObject> L = MakeShared<FJsonObject>();
		for (int32 I = 0; I < int32(ELine::Count); ++I)
		{
			if (Lines.Column[I] >= 0) L->SetStringField(LineIds[I], RopeColourwayId(Lines.Column[I]));
		}
		Root->SetObjectField(TEXT("lines"), L);
	}
	FString Text;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Text);
	FJsonSerializer::Serialize(Root, Writer);
	return Text;
}

// ---------------------------------------------------------------- on the boat

void FBoatSkin::ApplyTo(FBoatLivery& L, int32 BoatType) const
{
	if (Paint.Hull.IsSet()) L.Hull = Paint.Hull.GetValue();
	if (Paint.Deck.IsSet()) L.Deck = Paint.Deck.GetValue();
	if (Paint.NonSkid.IsSet()) L.NonSkid = Paint.NonSkid.GetValue();
	if (Paint.Bottom.IsSet()) L.Bottom = Paint.Bottom.GetValue();
	if (Paint.bBoot.IsSet()) L.bBoot = Paint.bBoot.GetValue();
	if (Paint.Boot.IsSet()) L.Boot = Paint.Boot.GetValue();
	if (!L.bBoot) L.Boot = L.Hull;          // as SampleBoatLivery: no stripe is the hull's own colour
	if (Paint.bCove.IsSet()) L.bCove = Paint.bCove.GetValue();
	if (Paint.Cove.IsSet() && !(Paint.bCove.IsSet() && !Paint.bCove.GetValue())) { L.bCove = true; L.Cove = Paint.Cove.GetValue(); }
	if (!L.bCove) L.Cove = L.Hull;
	if (Paint.bTrim.IsSet()) L.bTeak = Paint.bTrim.GetValue();   // (no trim: the rails take the deck's colour)
	if (Paint.Trim.IsSet() && !(Paint.bTrim.IsSet() && !Paint.bTrim.GetValue())) { L.bTeak = true; L.Teak = Paint.Trim.GetValue(); }
	if (Paint.bSparsPainted.IsSet()) L.bSparPainted = Paint.bSparsPainted.GetValue();
	if (Paint.Spars.IsSet()) L.Spar = Paint.Spars.GetValue();
	// The wear: the exact pair as M_BoatSurface's own ageing share (sat(Age / 20) x (1 - 0.6 Care): make_materials.py
	// BOAT_CODE), or the level's share. The club level leaves her as the class has her.
	if (Wear.AgeYears.IsSet())
	{
		SetLiveryWear(L, BoatType, FMath::Clamp(Wear.AgeYears.GetValue() / 20.f, 0.f, 1.f) * (1.f - 0.6f * Wear.Care.Get(0.5f)));
	}
	else if (Wear.Level >= 0 && Wear.Level != BoatSkinLocal::ClubLevel)
	{
		SetLiveryWear(L, BoatType, BoatSkinLocal::WearLevels[FMath::Min(Wear.Level, NumWearLevels - 1)].Share);
	}
	if (Sails.Number.IsSet()) L.SailNumber = Sails.Number.GetValue();
}

bool FBoatSkin::AgeCare(float& OutAgeYears, float& OutCare) const
{
	if (Wear.AgeYears.IsSet())
	{
		OutAgeYears = Wear.AgeYears.GetValue();
		OutCare = Wear.Care.Get(0.5f);
		return true;
	}
	if (Wear.Level < 0 || Wear.Level == BoatSkinLocal::ClubLevel) return false;
	const BoatSkinLocal::FWearLevel& W = BoatSkinLocal::WearLevels[FMath::Min(Wear.Level, NumWearLevels - 1)];
	OutAgeYears = W.Age;
	OutCare = W.Care;
	return true;
}

void FBoatSkin::RopeColumns(uint8* Out) const
{
	for (int32 I = 0; I < 256; ++I) Out[I] = uint8(I);
	for (int32 I = 0; I < int32(ELine::Count); ++I)
	{
		if (Lines.Column[I] >= 0 && Lines.Column[I] < NumRopeColourways()) Out[BoatSkinLocal::LineLooks[I]] = uint8(Lines.Column[I]);
	}
}

// ---------------------------------------------------------------- the store

FString BoatSkinStore::Dir()
{
	return FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / TEXT("Skins"));
}

TArray<FBoatSkin> BoatSkinStore::BuiltIn(int32 BoatType)
{
	using namespace BoatSkinLocal;
	TArray<FBoatSkin> Out;
	if (BoatType < 0 || BoatType >= int32(Sailing::EBoatType::Count)) return Out;
	// The catalogue's schemes in its own order (Inputs/g3/boat-catalogue.json), named for the two slice boats.
	static const TCHAR* const J22Names[][2] = { { TEXT("factory-white"), TEXT("Factory white") }, { TEXT("late-model"), TEXT("Late model") },
		{ TEXT("race-polished"), TEXT("Race polished") }, { TEXT("navy"), TEXT("Navy") }, { TEXT("red"), TEXT("Red") }, { TEXT("dark-grey"), TEXT("Dark grey") } };
	// (The Sunfish's red and blue deck stripes are not livery colours yet, so those two schemes are one skin: below.)
	static const TCHAR* const SunfishNames[][2] = { { TEXT("class-white"), TEXT("Class white") }, { TEXT("class-white-2"), TEXT("Class white 2") },
		{ TEXT("blue-deck"), TEXT("Blue deck") }, { TEXT("vintage-teal"), TEXT("Vintage teal") } };
	const bool bJ22 = BoatType == int32(Sailing::EBoatType::J22), bSunfish = BoatType == int32(Sailing::EBoatType::Sunfish);
	const int32 Named = bJ22 ? int32(UE_ARRAY_COUNT(J22Names)) : bSunfish ? int32(UE_ARRAY_COUNT(SunfishNames)) : 0;
	const int32 Schemes = NumLiverySchemes(BoatType);
	for (int32 I = 0; I < Schemes; ++I)
	{
		// A scheme whose paint a skin already carries (it differs only in what a livery does not hold) is not listed twice.
		const FBoatLivery L = LiveryForScheme(BoatType, I);
		bool bSeen = false;
		for (int32 J = 0; J < I && !bSeen; ++J)
		{
			const FBoatLivery E = LiveryForScheme(BoatType, J);
			bSeen = E.Hull.Equals(L.Hull) && E.Deck.Equals(L.Deck) && E.NonSkid.Equals(L.NonSkid) && E.Bottom.Equals(L.Bottom)
				&& E.bBoot == L.bBoot && E.Boot.Equals(L.Boot) && E.bCove == L.bCove && E.Cove.Equals(L.Cove) && E.bTeak == L.bTeak && E.Teak.Equals(L.Teak);
		}
		if (bSeen) continue;
		if (I < Named)
		{
			const TCHAR* const* N = bJ22 ? J22Names[I] : SunfishNames[I];
			// Race polished is the dry-sailed boat: new. The rest are club boats as the class is.
			Out.Add(MakeBuiltIn(BoatType, N[0], N[1], I, bJ22 && I == 2 ? 0 : ClubLevel));
		}
		else
		{
			Out.Add(MakeBuiltIn(BoatType, *FString::Printf(TEXT("scheme-%d"), I + 1), *FString::Printf(TEXT("Scheme %d"), I + 1), I, ClubLevel));
		}
	}
	if (Schemes > 0)
	{
		Out.Add(MakeBuiltIn(BoatType, TEXT("showroom"), TEXT("Showroom new"), 0, 0));
		Out.Add(MakeBuiltIn(BoatType, TEXT("well-loved"), TEXT("Well loved"), 0, 3));
		Out.Add(MakeBuiltIn(BoatType, TEXT("barn-find"), TEXT("Barn find"), 0, 4));
	}
	return Out;
}

TArray<FBoatSkin> BoatSkinStore::Mine(int32 BoatType)
{
	TArray<FBoatSkin> Out;
	const FString Boat = FSailSave::BoatId(BoatType);
	TArray<FString> Files;
	IFileManager::Get().FindFiles(Files, *(Dir() / TEXT("*.skin.json")), true, false);
	Files.Sort();
	for (const FString& File : Files)
	{
		const FString Path = Dir() / File;
		if (IFileManager::Get().FileSize(*Path) > FBoatSkin::MaxFileBytes)
		{
			SAIL_LOG(Log, TEXT("Skins: %s is over the size cap, skipped"), *File);
			continue;
		}
		FString Text, Message;
		FBoatSkin S;
		if (!FFileHelper::LoadFileToString(Text, *Path) || FBoatSkin::FromJson(Text, S, &Message) != FBoatSkin::EResult::Ok)
		{
			SAIL_LOG(Log, TEXT("Skins: %s skipped (%s)"), *File, *Message);
			continue;
		}
		// The file's name is its id (a renamed or copied file is still one skin). A name that is not an id as it stands
		// ("My_Navy") is left out: the skin could be listed but never found, saved over or deleted by that id.
		const FString Base = File.LeftChop(FCString::Strlen(BoatSkinLocal::FileSuffix));
		S.Id = FBoatSkin::CleanId(Base);
		if (!S.Id.Equals(Base, ESearchCase::CaseSensitive))
		{
			SAIL_LOG(Log, TEXT("Skins: %s skipped (name the file in lower-case letters, digits and hyphens)"), *File);
			continue;
		}
		if (S.Id.IsEmpty() || S.Id.StartsWith(BoatSkinLocal::BuiltInPrefix)) continue;
		if (!S.BoatId.IsEmpty() && S.BoatId != Boat) continue;
		Out.Add(MoveTemp(S));
	}
	Out.StableSort([](const FBoatSkin& A, const FBoatSkin& B) { return A.Name < B.Name; });
	return Out;
}

bool BoatSkinStore::Find(int32 BoatType, const FString& InId, FBoatSkin& Out)
{
	const FString Id = FBoatSkin::CleanId(InId);
	if (Id.IsEmpty()) return false;
	if (Id.StartsWith(BoatSkinLocal::BuiltInPrefix))
	{
		for (FBoatSkin& S : BuiltIn(BoatType))
		{
			if (S.Id == Id) { Out = MoveTemp(S); return true; }
		}
		return false;
	}
	const FString Path = BoatSkinLocal::FileOf(Id);
	FString Text;
	if (IFileManager::Get().FileSize(*Path) > FBoatSkin::MaxFileBytes || !FFileHelper::LoadFileToString(Text, *Path)) return false;
	if (FBoatSkin::FromJson(Text, Out) != FBoatSkin::EResult::Ok) return false;
	Out.Id = Id;
	return true;
}

bool BoatSkinStore::Save(const FBoatSkin& Skin)
{
	const FString Id = FBoatSkin::CleanId(Skin.Id);
	if (Id.IsEmpty() || Id.StartsWith(BoatSkinLocal::BuiltInPrefix)) return false;
	FBoatSkin Copy = Skin;
	Copy.Id = Id;
	Copy.Name = FBoatSkin::CleanName(Skin.Name);
	if (Copy.Name.IsEmpty()) Copy.Name = TEXT("Skin");
	return FSailSave::WriteAtomic(BoatSkinLocal::FileOf(Id), Copy.ToJson());
}

bool BoatSkinStore::Delete(const FString& InId)
{
	const FString Id = FBoatSkin::CleanId(InId);
	if (Id.IsEmpty() || Id.StartsWith(BoatSkinLocal::BuiltInPrefix)) return false;
	return IFileManager::Get().Delete(*BoatSkinLocal::FileOf(Id), false, false, true);
}

FString BoatSkinStore::FreeId(const FString& Name)
{
	FString Base = FBoatSkin::CleanId(Name);
	if (Base.IsEmpty() || Base.StartsWith(BoatSkinLocal::BuiltInPrefix)) Base = TEXT("skin");
	// Windows keeps some names for devices whatever follows the dot ("con.skin.json" cannot be written).
	for (const TCHAR* Device : { TEXT("con"), TEXT("prn"), TEXT("aux"), TEXT("nul") }) if (Base == Device) Base = TEXT("skin-") + Base;
	if (Base.Len() == 4 && (Base.StartsWith(TEXT("com")) || Base.StartsWith(TEXT("lpt"))) && FChar::IsDigit(Base[3])) Base = TEXT("skin-") + Base;
	Base.LeftInline(FBoatSkin::MaxIdChars - 4);
	FString Id = Base;
	for (int32 N = 2; N < 1000 && IFileManager::Get().FileExists(*BoatSkinLocal::FileOf(Id)); ++N) Id = FString::Printf(TEXT("%s-%d"), *Base, N);
	return Id;
}

bool BoatSkinStore::Active(int32 BoatType, FBoatSkin& Out)
{
	// Stills and tests: -SailingSkin=<id> (a built-in's or a file's).
	FString Arg;
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingSkin="), Arg, false) && !Arg.IsEmpty()) return Find(BoatType, Arg, Out);
	const FString Chosen = SailSaveStore::BoatSkin(FSailSave::BoatId(BoatType));
	return !Chosen.IsEmpty() && Find(BoatType, Chosen, Out);
}
