#include "Misc/AutomationTest.h"
#include "BoatSkin.h"
#include "BoatLivery.h"
#include "BoatModel.h"
#include "SailSave.h"
#include "SkinEditor.h"
#include "UI/SailFrontEnd.h"
#include "Framework/Application/SlateApplication.h"
#include "Input/Events.h"
#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

// Boat skins (docs/skins/README.md): a skin round-trips through its JSON, the reader clamps and drops what it should and
// refuses what it must, a skin changes only the livery fields it names, the built-ins exist for every class, the rope
// colourway ids match the texture's order, and the save keeps which skin each boat wears.
namespace SailSkinTestsLocal
{
	constexpr EAutomationTestFlags SkinFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

	TSharedPtr<FJsonObject> Parse(const FString& Text)
	{
		TSharedPtr<FJsonObject> Root;
		FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root);
		return Root;
	}

	FBoatSkin Everything()
	{
		FBoatSkin S;
		S.Id = TEXT("my-navy");
		S.Name = TEXT("My navy");
		S.BoatId = TEXT("J22");
		FLinearColor C;
		FBoatSkin::ParseHex(TEXT("#1C2A44"), C); S.Paint.Hull = C;
		FBoatSkin::ParseHex(TEXT("#F2F0EA"), C); S.Paint.Deck = C;
		FBoatSkin::ParseHex(TEXT("#D9D7D0"), C); S.Paint.NonSkid = C;
		FBoatSkin::ParseHex(TEXT("#2E4F8A"), C); S.Paint.Bottom = C;
		FBoatSkin::ParseHex(TEXT("#B3201B"), C); S.Paint.Boot = C; S.Paint.bBoot = true;
		FBoatSkin::ParseHex(TEXT("#D9B33A"), C); S.Paint.Cove = C;
		FBoatSkin::ParseHex(TEXT("#9A6233"), C); S.Paint.Trim = C;
		FBoatSkin::ParseHex(TEXT("#17191C"), C); S.Paint.Spars = C; S.Paint.bSparsPainted = true;
		S.Wear.Level = 4;
		FBoatSkin::ParseHex(TEXT("#EDE6D3"), C); S.Sails.Cloth = C;
		S.Sails.Number = FString(TEXT("402"));
		S.Sails.bClassMark = false;
		S.Lines.Column[int32(FBoatSkin::ELine::Mainsheet)] = 7;
		S.Lines.Column[int32(FBoatSkin::ELine::JibPort)] = 1;
		S.Lines.Column[int32(FBoatSkin::ELine::JibStarboard)] = 2;
		S.Lines.Column[int32(FBoatSkin::ELine::Control)] = 10;
		return S;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSkinRoundTripTest, "SailingSim.Skin.RoundTrip", SailSkinTestsLocal::SkinFlags)
bool FSailingSkinRoundTripTest::RunTest(const FString&)
{
	using namespace SailSkinTestsLocal;
	const FBoatSkin In = Everything();
	const FString Text = In.ToJson();
	FBoatSkin Out;
	FString Message;
	TestEqual(TEXT("Reads its own text"), int32(FBoatSkin::FromJson(Text, Out, &Message)), int32(FBoatSkin::EResult::Ok));
	TestEqual(TEXT("Same text again"), Out.ToJson(), Text);
	TestEqual(TEXT("Id"), Out.Id, In.Id);
	TestEqual(TEXT("Name"), Out.Name, In.Name);
	TestEqual(TEXT("Boat"), Out.BoatId, In.BoatId);
	TestEqual(TEXT("Hull"), FBoatSkin::ToHex(Out.Paint.Hull.Get(FLinearColor::Black)), FString(TEXT("#1C2A44")));
	TestEqual(TEXT("Spars"), FBoatSkin::ToHex(Out.Paint.Spars.Get(FLinearColor::Black)), FString(TEXT("#17191C")));
	TestEqual(TEXT("Wear level"), Out.Wear.Level, 4);
	TestEqual(TEXT("Sail number"), Out.Sails.Number.Get(FString()), FString(TEXT("402")));
	TestTrue(TEXT("Class mark off"), Out.Sails.bClassMark.IsSet() && !Out.Sails.bClassMark.GetValue());
	TestEqual(TEXT("Mainsheet colourway"), Out.Lines.Column[0], 7);
	TestEqual(TEXT("Control colourway"), Out.Lines.Column[3], 10);
	// Every colour survives hex both ways.
	for (const TCHAR* Hex : { TEXT("#000000"), TEXT("#FFFFFF"), TEXT("#F2F0EA"), TEXT("#1C2A44"), TEXT("#8E1C1C"), TEXT("#7DB046") })
	{
		FLinearColor C;
		TestTrue(Hex, FBoatSkin::ParseHex(Hex, C));
		TestEqual(Hex, FBoatSkin::ToHex(C), FString(Hex));
	}
	// A skin with only a sail colour writes only that section, and reads back with the rest unset.
	FBoatSkin Sails;
	Sails.Id = TEXT("cream");
	Sails.Name = TEXT("Cream");
	FLinearColor Cream;
	FBoatSkin::ParseHex(TEXT("#EDE6D3"), Cream);
	Sails.Sails.Cloth = Cream;
	const TSharedPtr<FJsonObject> Root = Parse(Sails.ToJson());
	TestTrue(TEXT("Parses"), Root.IsValid());
	if (Root.IsValid())
	{
		TestTrue(TEXT("Has sails"), Root->HasField(TEXT("sails")));
		TestFalse(TEXT("No paint"), Root->HasField(TEXT("paint")));
		TestFalse(TEXT("No wear"), Root->HasField(TEXT("wear")));
		TestFalse(TEXT("No lines"), Root->HasField(TEXT("lines")));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSkinBadFilesTest, "SailingSim.Skin.BadFiles", SailSkinTestsLocal::SkinFlags)
bool FSailingSkinBadFilesTest::RunTest(const FString&)
{
	FBoatSkin Out;
	FString Message;
	TestEqual(TEXT("Not JSON"), int32(FBoatSkin::FromJson(TEXT("not json {"), Out, &Message)), int32(FBoatSkin::EResult::Invalid));
	TestEqual(TEXT("Another file"), int32(FBoatSkin::FromJson(TEXT("{\"version\":1,\"game\":\"SailingSim\"}"), Out, &Message)), int32(FBoatSkin::EResult::Invalid));
	TestEqual(TEXT("No version"), int32(FBoatSkin::FromJson(TEXT("{\"format\":\"ready-about-skin\"}"), Out, &Message)), int32(FBoatSkin::EResult::Invalid));
	TestEqual(TEXT("Newer version"), int32(FBoatSkin::FromJson(TEXT("{\"format\":\"ready-about-skin\",\"version\":99}"), Out, &Message)), int32(FBoatSkin::EResult::Refused));
	// Over the size cap: refused before it is parsed.
	FString Big = TEXT("{\"format\":\"ready-about-skin\",\"version\":1,\"name\":\"");
	while (Big.Len() <= FBoatSkin::MaxFileBytes) Big += TEXT("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
	Big += TEXT("\"}");
	TestEqual(TEXT("Too large"), int32(FBoatSkin::FromJson(Big, Out, &Message)), int32(FBoatSkin::EResult::Refused));

	// Hostile or sloppy fields: nothing fails, everything is clamped, cleaned or dropped.
	const FString Sloppy = TEXT("{\"format\":\"ready-about-skin\",\"version\":1,")
		TEXT("\"id\":\"../../Config/Evil Skin!!\",\"name\":\"<b>Rude</b> name that is far too long to fit on a card\",\"boat\":\"Titanic\",")
		TEXT("\"paint\":{\"hull\":\"red\",\"deck\":\"#12345\",\"bottom\":\"#GGGGGG\",\"boot\":\"none\",\"spars\":\"bare\",\"nonSkid\":42,\"material\":\"/Game/Evil\"},")
		TEXT("\"wear\":{\"level\":\"radioactive\",\"ageYears\":1e9,\"care\":-5},")
		TEXT("\"sails\":{\"cloth\":\"#FFFFFF\",\"number\":\"USA 12345678901\",\"classMark\":\"yes\"},")
		TEXT("\"lines\":{\"mainsheet\":\"chrome\",\"jibPort\":\"red_white_fleck\"},\"script\":\"rm -rf\"}");
	TestEqual(TEXT("Sloppy file reads"), int32(FBoatSkin::FromJson(Sloppy, Out, &Message)), int32(FBoatSkin::EResult::Ok));
	TestEqual(TEXT("Id cleaned"), Out.Id, FString(TEXT("config-evil-skin")));
	TestTrue(TEXT("Name cleaned and cut"), Out.Name.Len() <= FBoatSkin::MaxNameChars && !Out.Name.Contains(TEXT("<")) && !Out.Name.Contains(TEXT(">")));
	TestTrue(TEXT("Unknown boat dropped"), Out.BoatId.IsEmpty());
	TestFalse(TEXT("Bad hull colour dropped"), Out.Paint.Hull.IsSet());
	TestFalse(TEXT("Short hex dropped"), Out.Paint.Deck.IsSet());
	TestFalse(TEXT("Bad hex digits dropped"), Out.Paint.Bottom.IsSet());
	TestFalse(TEXT("Number as a colour dropped"), Out.Paint.NonSkid.IsSet());
	TestTrue(TEXT("Boot stripe off"), Out.Paint.bBoot.IsSet() && !Out.Paint.bBoot.GetValue());
	TestTrue(TEXT("Spars bare"), Out.Paint.bSparsPainted.IsSet() && !Out.Paint.bSparsPainted.GetValue());
	TestEqual(TEXT("Unknown wear level"), Out.Wear.Level, -1);
	TestEqual(TEXT("Age clamped"), Out.Wear.AgeYears.Get(-1.f), 60.f);
	TestEqual(TEXT("Care clamped"), Out.Wear.Care.Get(-1.f), 0.f);
	TestEqual(TEXT("Sail number digits, capped"), Out.Sails.Number.Get(FString()), FString(TEXT("123456")));
	TestFalse(TEXT("Class mark of the wrong type dropped"), Out.Sails.bClassMark.IsSet());
	TestEqual(TEXT("Unknown colourway dropped"), Out.Lines.Column[0], -1);
	TestEqual(TEXT("Known colourway kept"), Out.Lines.Column[1], 1);
	// What it writes back carries none of the junk.
	const FString Back = Out.ToJson();
	TestFalse(TEXT("No script"), Back.Contains(TEXT("script")));
	TestFalse(TEXT("No material"), Back.Contains(TEXT("material")));
	TestFalse(TEXT("No path"), Back.Contains(TEXT("..")));

	// A file cannot claim to be a built-in.
	TestEqual(TEXT("Built-in id reads"), int32(FBoatSkin::FromJson(TEXT("{\"format\":\"ready-about-skin\",\"version\":1,\"id\":\"builtin-j22-navy\"}"), Out, &Message)), int32(FBoatSkin::EResult::Ok));
	TestFalse(TEXT("Not a built-in id"), Out.Id.StartsWith(TEXT("builtin-")));
	TestFalse(TEXT("Not marked built-in"), Out.bBuiltIn);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSkinApplyTest, "SailingSim.Skin.Apply", SailSkinTestsLocal::SkinFlags)
bool FSailingSkinApplyTest::RunTest(const FString&)
{
	using namespace SailSkinTestsLocal;
	const int32 J22 = int32(Sailing::EBoatType::J22);
	const FBoatLivery Base = SampleBoatLivery(J22, 0);

	// An empty skin changes nothing.
	{
		FBoatLivery L = Base;
		FBoatSkin().ApplyTo(L, J22);
		TestTrue(TEXT("Empty: hull"), L.Hull.Equals(Base.Hull));
		TestTrue(TEXT("Empty: deck"), L.Deck.Equals(Base.Deck));
		TestTrue(TEXT("Empty: boot"), L.bBoot == Base.bBoot && L.Boot.Equals(Base.Boot));
		TestTrue(TEXT("Empty: wear"), L.Wear == Base.Wear);
		TestEqual(TEXT("Empty: fade"), L.SailFade, Base.SailFade);
		TestEqual(TEXT("Empty: number"), L.SailNumber, Base.SailNumber);
		TestTrue(TEXT("Empty: spars"), L.bSparPainted == Base.bSparPainted && L.Spar.Equals(Base.Spar));
		float Age = 0.f, Care = 0.f;
		TestFalse(TEXT("Empty: no age"), FBoatSkin().AgeCare(Age, Care));
		uint8 Columns[256];
		FBoatSkin().RopeColumns(Columns);
		bool bIdentity = true;
		for (int32 I = 0; I < 256; ++I) bIdentity = bIdentity && Columns[I] == uint8(I);
		TestTrue(TEXT("Empty: every rope look keeps its column"), bIdentity);
	}
	// A sails-only skin leaves the paint alone.
	{
		FBoatLivery L = Base;
		FBoatSkin S;
		S.Sails.Number = FString(TEXT("77"));
		S.ApplyTo(L, J22);
		TestEqual(TEXT("Sails only: number"), L.SailNumber, FString(TEXT("77")));
		TestTrue(TEXT("Sails only: hull kept"), L.Hull.Equals(Base.Hull));
		TestTrue(TEXT("Sails only: wear kept"), L.Wear == Base.Wear);
	}
	// Everything: each field lands, and nothing else moves.
	{
		FBoatLivery L = Base;
		const FBoatSkin S = Everything();
		S.ApplyTo(L, J22);
		TestEqual(TEXT("Hull"), FBoatSkin::ToHex(L.Hull), FString(TEXT("#1C2A44")));
		TestEqual(TEXT("Bottom"), FBoatSkin::ToHex(L.Bottom), FString(TEXT("#2E4F8A")));
		TestTrue(TEXT("Boot on"), L.bBoot);
		TestEqual(TEXT("Boot"), FBoatSkin::ToHex(L.Boot), FString(TEXT("#B3201B")));
		TestTrue(TEXT("Cove on"), L.bCove);
		TestTrue(TEXT("Trim on"), L.bTeak);
		TestTrue(TEXT("Spars painted"), L.bSparPainted);
		TestEqual(TEXT("Spars"), FBoatSkin::ToHex(L.Spar), FString(TEXT("#17191C")));
		TestEqual(TEXT("Number"), L.SailNumber, FString(TEXT("402")));
		TestEqual(TEXT("Scheme kept"), L.Scheme, Base.Scheme);
		// Neglected: every channel at the top of the class's club range, so at least the club boat's.
		for (int32 K = 0; K < 4; ++K) TestTrue(FString::Printf(TEXT("Neglected wear channel %d"), K), L.Wear[K] >= Base.Wear[K] - 1e-4f && L.Wear[K] <= 1.f);
		float Age = 0.f, Care = 1.f;
		TestTrue(TEXT("Neglected has an age"), S.AgeCare(Age, Care));
		TestEqual(TEXT("Neglected age"), Age, 20.f);
		TestEqual(TEXT("Neglected care"), Care, 0.1f);
		uint8 Columns[256];
		S.RopeColumns(Columns);
		TestEqual(TEXT("Mainsheet look 0 draws column 7"), int32(Columns[0]), 7);
		TestEqual(TEXT("Port jib sheet look 1"), int32(Columns[1]), 1);
		TestEqual(TEXT("Starboard jib sheet look 2"), int32(Columns[2]), 2);
		TestEqual(TEXT("Control lines look 5 draws column 10"), int32(Columns[5]), 10);
		TestEqual(TEXT("The plain look is left alone"), int32(Columns[255]), 255);
	}
	// "none" takes the boot stripe off: it takes the hull's colour, as the catalogue's stripeless schemes do.
	{
		FBoatLivery L = Base;
		FBoatSkin S;
		FLinearColor Red;
		FBoatSkin::ParseHex(TEXT("#8E1C1C"), Red);
		S.Paint.Hull = Red;
		S.Paint.bBoot = false;
		S.ApplyTo(L, J22);
		TestFalse(TEXT("Boot off"), L.bBoot);
		TestTrue(TEXT("Boot is the hull's colour"), L.Boot.Equals(L.Hull));
	}
	// Wear levels: new is clean, the club level is the class's own boat, and the ladder never gets cleaner going down
	// from new to neglected at its ends.
	{
		FBoatSkin S;
		FBoatLivery New = Base, Club = Base, Worst = Base;
		S.Wear.Level = 0; S.ApplyTo(New, J22);
		S.Wear.Level = 2; S.ApplyTo(Club, J22);
		S.Wear.Level = 4; S.ApplyTo(Worst, J22);
		for (int32 K = 0; K < 4; ++K)
		{
			TestEqual(FString::Printf(TEXT("New channel %d"), K), New.Wear[K], 0.f);
			TestEqual(FString::Printf(TEXT("Club channel %d"), K), Club.Wear[K], Base.Wear[K]);
			TestTrue(FString::Printf(TEXT("Neglected channel %d"), K), Worst.Wear[K] >= Club.Wear[K] - 1e-4f);
		}
		float Age = -1.f, Care = -1.f;
		S.Wear.Level = 2;
		TestFalse(TEXT("Club level leaves Age unset"), S.AgeCare(Age, Care));
		S.Wear.Level = 0;
		TestTrue(TEXT("New has an age"), S.AgeCare(Age, Care));
		TestEqual(TEXT("New age"), Age, 0.f);
		// The exact pair beats the level.
		S.Wear.AgeYears = 12.f;
		S.Wear.Care = 0.25f;
		TestTrue(TEXT("Exact pair"), S.AgeCare(Age, Care));
		TestEqual(TEXT("Exact age"), Age, 12.f);
		TestEqual(TEXT("Exact care"), Care, 0.25f);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSkinBuiltInTest, "SailingSim.Skin.BuiltIn", SailSkinTestsLocal::SkinFlags)
bool FSailingSkinBuiltInTest::RunTest(const FString&)
{
	for (int32 T = 0; T < int32(Sailing::EBoatType::Count); ++T)
	{
		const TArray<FBoatSkin> Skins = BoatSkinStore::BuiltIn(T);
		if (NumLiverySchemes(T) == 0) { TestEqual(FString::Printf(TEXT("class %d without schemes has no skins"), T), Skins.Num(), 0); continue; }
		TestTrue(FString::Printf(TEXT("class %d has built-in skins"), T), Skins.Num() >= 4);
		TSet<FString> Ids, Names;
		for (const FBoatSkin& S : Skins)
		{
			TestTrue(S.Id, S.bBuiltIn && S.Id.StartsWith(TEXT("builtin-")) && S.Id == FBoatSkin::CleanId(S.Id));
			TestEqual(S.Id + TEXT(" boat"), S.BoatId, FSailSave::BoatId(T));
			TestFalse(S.Id + TEXT(" id twice"), Ids.Contains(S.Id));
			TestFalse(S.Id + TEXT(" name twice"), Names.Contains(S.Name));
			Ids.Add(S.Id);
			Names.Add(S.Name);
			TestTrue(S.Id + TEXT(" has a hull colour"), S.Paint.Hull.IsSet());
			// Found again by id, and never written or deleted as a file.
			FBoatSkin Found;
			TestTrue(S.Id + TEXT(" found"), BoatSkinStore::Find(T, S.Id, Found) && Found.Name == S.Name);
			TestFalse(S.Id + TEXT(" not saved over"), BoatSkinStore::Save(S));
			TestFalse(S.Id + TEXT(" not deleted"), BoatSkinStore::Delete(S.Id));
			// A built-in survives its own JSON as a copy (a file never makes a built-in).
			FBoatSkin Copy;
			TestEqual(S.Id + TEXT(" as a file"), int32(FBoatSkin::FromJson(S.ToJson(), Copy)), int32(FBoatSkin::EResult::Ok));
			TestFalse(S.Id + TEXT(" copy is not built in"), Copy.bBuiltIn || Copy.Id.StartsWith(TEXT("builtin-")));
		}
	}
	// The slice boats: the J/22's six catalogue schemes and the three wear looks; the Sunfish's by paint.
	TestEqual(TEXT("J/22 skins"), BoatSkinStore::BuiltIn(int32(Sailing::EBoatType::J22)).Num(), 9);
	FBoatSkin Navy;
	TestTrue(TEXT("J/22 navy"), BoatSkinStore::Find(int32(Sailing::EBoatType::J22), TEXT("builtin-j22-navy"), Navy));
	TestEqual(TEXT("Navy's hull is the catalogue's"), FBoatSkin::ToHex(Navy.Paint.Hull.Get(FLinearColor::White)), FString(TEXT("#1C2A44")));
	FBoatSkin Missing;
	TestFalse(TEXT("Another class's built-in is not found"), BoatSkinStore::Find(int32(Sailing::EBoatType::Sunfish), TEXT("builtin-j22-navy"), Missing));
	TestFalse(TEXT("A path is not an id"), BoatSkinStore::Find(0, TEXT("../SaveGames/profile"), Missing));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSkinRopeColourwaysTest, "SailingSim.Skin.RopeColourways", SailSkinTestsLocal::SkinFlags)
bool FSailingSkinRopeColourwaysTest::RunTest(const FString&)
{
	// The ids are T_RopeColourways' columns in Inputs/rope/colourways.json order (the repo's file; absent in a packaged run).
	FString Text;
	const FString File = FPaths::ProjectDir() / TEXT("Inputs/rope/colourways.json");
	if (!FFileHelper::LoadFileToString(Text, *File))
	{
		AddInfo(TEXT("Inputs/rope/colourways.json not here: order not checked"));
		return true;
	}
	const TSharedPtr<FJsonObject> Root = SailSkinTestsLocal::Parse(Text);
	const TArray<TSharedPtr<FJsonValue>>* Ways = nullptr;
	if (!TestTrue(TEXT("colourways.json parses"), Root.IsValid() && Root->TryGetArrayField(TEXT("colourways"), Ways) && Ways)) return false;
	TestEqual(TEXT("Colourway count"), FBoatSkin::NumRopeColourways(), Ways->Num());
	for (int32 I = 0; I < Ways->Num() && I < FBoatSkin::NumRopeColourways(); ++I)
	{
		const TSharedPtr<FJsonObject>* Way = nullptr;
		FString Name;
		if ((*Ways)[I].IsValid() && (*Ways)[I]->TryGetObject(Way) && Way) (*Way)->TryGetStringField(TEXT("name"), Name);
		TestEqual(FString::Printf(TEXT("Column %d"), I), FString(FBoatSkin::RopeColourwayId(I)), Name);
		TestEqual(FString::Printf(TEXT("Column %d by id"), I), FBoatSkin::RopeColourwayIndex(Name), I);
	}
	TestEqual(TEXT("Unknown colourway"), FBoatSkin::RopeColourwayIndex(TEXT("chrome")), -1);
	for (int32 L = 0; L < FBoatSkin::NumWearLevels; ++L) TestEqual(FString::Printf(TEXT("Wear level %d by id"), L), FBoatSkin::WearLevelIndex(FBoatSkin::WearLevelId(L)), L);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSkinSaveFieldTest, "SailingSim.Skin.SaveField", SailSkinTestsLocal::SkinFlags)
bool FSailingSkinSaveFieldTest::RunTest(const FString&)
{
	using namespace SailSkinTestsLocal;
	// The save records which skin each boat wears, and an older file without the field reads as no skins.
	FSailSave S;
	S.WrittenAt = FDateTime(2026, 11, 13, 12, 0, 0);
	const FString Plain = S.ToJson();
	TestFalse(TEXT("No boats field without a skin"), Parse(Plain)->HasField(TEXT("boats")));
	S.BoatSkins.Add(TEXT("J22"), TEXT("my-navy"));
	S.BoatSkins.Add(TEXT("Sunfish"), TEXT("builtin-sunfish-blue-deck"));
	FSailSave Out;
	TestEqual(TEXT("Reads"), int32(FSailSave::FromJson(S.ToJson(), Out)), int32(FSailSave::EResult::Ok));
	TestEqual(TEXT("Two boats"), Out.BoatSkins.Num(), 2);
	TestEqual(TEXT("J/22's skin"), Out.BoatSkins.FindRef(TEXT("J22")), FString(TEXT("my-navy")));
	TestEqual(TEXT("Sunfish's skin"), Out.BoatSkins.FindRef(TEXT("Sunfish")), FString(TEXT("builtin-sunfish-blue-deck")));
	FSailSave Old;
	TestEqual(TEXT("A file without the field"), int32(FSailSave::FromJson(Plain, Old)), int32(FSailSave::EResult::Ok));
	TestEqual(TEXT("No skins"), Old.BoatSkins.Num(), 0);
	// Taking a skin off is written (the file's own copy does not bring it back), and what the game does not know about a
	// boat is kept.
	const FString Known = TEXT("{\"version\":1,\"game\":\"SailingSim\",\"boats\":{\"J22\":{\"skin\":\"my-navy\",\"hours\":12.5},\"Hobie16\":{\"skin\":\"old\"}}}");
	FSailSave Loaded;
	TestEqual(TEXT("Reads a file with more"), int32(FSailSave::FromJson(Known, Loaded)), int32(FSailSave::EResult::Ok));
	TestEqual(TEXT("J/22 from the file"), Loaded.BoatSkins.FindRef(TEXT("J22")), FString(TEXT("my-navy")));
	Loaded.BoatSkins.Remove(TEXT("J22"));
	Loaded.BoatSkins.Add(TEXT("Hobie16"), TEXT("new"));
	const TSharedPtr<FJsonObject> Back = Parse(Loaded.ToJson());
	const TSharedPtr<FJsonObject>* Boats = nullptr;
	if (TestTrue(TEXT("boats written"), Back.IsValid() && Back->TryGetObjectField(TEXT("boats"), Boats) && Boats))
	{
		const TSharedPtr<FJsonObject>* J22 = nullptr;
		if (TestTrue(TEXT("J/22 kept for its other fields"), (*Boats)->TryGetObjectField(TEXT("J22"), J22) && J22))
		{
			TestFalse(TEXT("J/22's skin is off"), (*J22)->HasField(TEXT("skin")));
			TestEqual(TEXT("J/22's unknown field kept"), (*J22)->GetNumberField(TEXT("hours")), 12.5);
		}
		const TSharedPtr<FJsonObject>* Hobie = nullptr;
		if (TestTrue(TEXT("Hobie written"), (*Boats)->TryGetObjectField(TEXT("Hobie16"), Hobie) && Hobie))
		{
			TestEqual(TEXT("Hobie's new skin"), (*Hobie)->GetStringField(TEXT("skin")), FString(TEXT("new")));
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSkinIdsTest, "SailingSim.Skin.Ids", SailSkinTestsLocal::SkinFlags)
bool FSailingSkinIdsTest::RunTest(const FString&)
{
	TestEqual(TEXT("Spaces to hyphens"), FBoatSkin::CleanId(TEXT("My Navy  Boat")), FString(TEXT("my-navy-boat")));
	TestEqual(TEXT("No path"), FBoatSkin::CleanId(TEXT("..\\..\\Windows/System32")), FString(TEXT("windows-system32")));
	TestEqual(TEXT("Nothing left"), FBoatSkin::CleanId(TEXT("!!!")), FString());
	TestTrue(TEXT("Capped"), FBoatSkin::CleanId(FString::ChrN(200, TEXT('a'))).Len() == FBoatSkin::MaxIdChars);
	TestEqual(TEXT("Name keeps case and marks"), FBoatSkin::CleanName(TEXT("  Bean's J/22, No. 7 ")), FString(TEXT("Bean's J/22, No. 7")));
	TestEqual(TEXT("Name drops markup"), FBoatSkin::CleanName(TEXT("<i>Fast</i>")), FString(TEXT("iFast/i")));
	FLinearColor C;
	TestFalse(TEXT("No hash"), FBoatSkin::ParseHex(TEXT("1C2A44"), C));
	TestFalse(TEXT("Eight digits"), FBoatSkin::ParseHex(TEXT("#1C2A44FF"), C));
	TestFalse(TEXT("Empty"), FBoatSkin::ParseHex(TEXT(""), C));
	TestTrue(TEXT("Lower case"), FBoatSkin::ParseHex(TEXT("#1c2a44"), C));
	return true;
}

// The Customize screen's editing (SkinEditor.h): a draft over the class's look, every change undoable, a dragged value one
// step, and what Use would do with it.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSkinEditorTest, "SailingSim.Skin.Editor", SailSkinTestsLocal::SkinFlags)
bool FSailingSkinEditorTest::RunTest(const FString&)
{
	const int32 J22 = int32(Sailing::EBoatType::J22);
	FSkinEditor Ed;
	Ed.OpenWith(J22, nullptr);
	TestFalse(TEXT("The class look is not dirty"), Ed.IsDirty());
	TestFalse(TEXT("Nothing to undo at the start"), Ed.CanUndo());
	TestEqual(TEXT("The class look saves as no skin"), int32(Ed.SavePlan()), int32(FSkinEditor::ESavePlan::ClassLook));
	TestEqual(TEXT("Made for the J/22"), Ed.GetDraft().BoatId, FString(TEXT("J22")));

	FLinearColor Navy, Red;
	FBoatSkin::ParseHex(TEXT("#1C2A44"), Navy);
	FBoatSkin::ParseHex(TEXT("#B3201B"), Red);
	const uint32 Rev0 = Ed.GetRevision();
	Ed.SetPartColour(FSkinEditor::EPart::Hull, Navy);
	TestTrue(TEXT("A change moves the revision"), Ed.GetRevision() != Rev0);
	TestTrue(TEXT("Dirty after a change"), Ed.IsDirty());
	TestEqual(TEXT("Hull"), FBoatSkin::ToHex(Ed.PartColour(FSkinEditor::EPart::Hull).Get(FLinearColor::White)), FString(TEXT("#1C2A44")));
	TestEqual(TEXT("A look made from nothing is a new file"), int32(Ed.SavePlan()), int32(FSkinEditor::ESavePlan::NewFile));
	TestEqual(TEXT("Its name"), Ed.NewName(), FString(TEXT("My look")));

	// A dragged slider (the same part again and again) is one undo step; another part is another.
	for (int32 K = 0; K < 20; ++K) Ed.SetPartColour(FSkinEditor::EPart::Hull, FLinearColor(0.01f * K, 0.1f, 0.2f), true);
	Ed.SetPartColour(FSkinEditor::EPart::Boot, Red);
	TestTrue(TEXT("The boot stripe is on"), Ed.GetDraft().Paint.bBoot.Get(false));
	TestTrue(TEXT("Undo the boot stripe"), Ed.Undo());
	TestFalse(TEXT("Boot back to the class's"), Ed.PartColour(FSkinEditor::EPart::Boot).IsSet());
	TestTrue(TEXT("Undo the drag"), Ed.Undo());
	TestEqual(TEXT("The drag is one step: the hull is the swatch again"), FBoatSkin::ToHex(Ed.PartColour(FSkinEditor::EPart::Hull).Get(FLinearColor::White)), FString(TEXT("#1C2A44")));
	TestTrue(TEXT("Undo the swatch"), Ed.Undo());
	TestFalse(TEXT("Hull back to the class's"), Ed.PartColour(FSkinEditor::EPart::Hull).IsSet());
	TestFalse(TEXT("Nothing more to undo"), Ed.CanUndo());
	TestFalse(TEXT("Clean again"), Ed.IsDirty());
	// Two picks of a swatch for one part are two steps (only a drag folds).
	Ed.SetPartColour(FSkinEditor::EPart::Deck, Navy);
	Ed.SetPartColour(FSkinEditor::EPart::Deck, Red);
	TestTrue(TEXT("Undo the second pick"), Ed.Undo());
	TestEqual(TEXT("The first pick is back"), FBoatSkin::ToHex(Ed.PartColour(FSkinEditor::EPart::Deck).Get(FLinearColor::White)), FString(TEXT("#1C2A44")));
	TestTrue(TEXT("Undo the first pick"), Ed.Undo());
	TestTrue(TEXT("Redo the first pick"), Ed.Redo());
	TestTrue(TEXT("Redo the second pick"), Ed.Redo());
	TestFalse(TEXT("Nothing more to redo"), Ed.CanRedo());
	// A change after an undo drops what was undone.
	Ed.Undo();
	Ed.SetWearLevel(4);
	TestFalse(TEXT("No redo after a new change"), Ed.CanRedo());
	TestEqual(TEXT("Wear"), Ed.GetDraft().Wear.Level, 4);

	// Off and clear.
	Ed.SetPartOff(FSkinEditor::EPart::Boot);
	TestTrue(TEXT("Boot off"), Ed.IsPartOff(FSkinEditor::EPart::Boot));
	Ed.SetPartOff(FSkinEditor::EPart::Hull);
	TestFalse(TEXT("A hull can't be off"), Ed.IsPartOff(FSkinEditor::EPart::Hull));
	Ed.ClearPart(FSkinEditor::EPart::Boot);
	TestFalse(TEXT("Boot cleared"), Ed.IsPartOff(FSkinEditor::EPart::Boot) || Ed.GetDraft().Paint.bBoot.IsSet());
	// Sails and lines.
	Ed.SetSailNumber(FString(TEXT("USA 1288 x")));
	TestEqual(TEXT("Digits only"), Ed.GetDraft().Sails.Number.Get(FString()), FString(TEXT("1288")));
	Ed.SetSailNumber(TOptional<FString>());
	TestFalse(TEXT("Class number again"), Ed.GetDraft().Sails.Number.IsSet());
	Ed.SetLine(FBoatSkin::ELine::Mainsheet, 7);
	Ed.SetLine(FBoatSkin::ELine::Control, 99);
	TestEqual(TEXT("Mainsheet colourway"), Ed.GetDraft().Lines.Column[0], 7);
	TestEqual(TEXT("A colourway out of range is the boat's own"), Ed.GetDraft().Lines.Column[3], -1);
	// The undo stack is bounded.
	for (int32 K = 0; K < 3 * FSkinEditor::MaxUndo; ++K) Ed.SetWearLevel(K % 5);
	int32 Undone = 0;
	while (Ed.Undo()) ++Undone;
	TestEqual(TEXT("Undo is capped"), Undone, FSkinEditor::MaxUndo);

	// From a built-in: unchanged it is named in the save; changed it becomes the player's own file, named after it.
	FBoatSkin NavySkin;
	if (TestTrue(TEXT("The navy built-in"), BoatSkinStore::Find(J22, TEXT("builtin-j22-navy"), NavySkin)))
	{
		Ed.OpenWith(J22, &NavySkin);
		TestEqual(TEXT("Unchanged built-in"), int32(Ed.SavePlan()), int32(FSkinEditor::ESavePlan::Existing));
		TestTrue(TEXT("Loaded is built in"), Ed.IsLoadedBuiltIn());
		Ed.SetLine(FBoatSkin::ELine::Mainsheet, 7);
		TestEqual(TEXT("Changed built-in"), int32(Ed.SavePlan()), int32(FSkinEditor::ESavePlan::NewFile));
		TestEqual(TEXT("Named after it"), Ed.NewName(), FString(TEXT("My navy")));
		// One of the player's own, changed, is written over.
		FBoatSkin Mine = NavySkin;
		Mine.bBuiltIn = false;
		Mine.Id = TEXT("my-navy");
		Mine.Name = TEXT("My navy");
		Ed.OpenWith(J22, &Mine);
		TestEqual(TEXT("Unchanged own skin"), int32(Ed.SavePlan()), int32(FSkinEditor::ESavePlan::Existing));
		Ed.SetWearLevel(0);
		TestEqual(TEXT("Changed own skin"), int32(Ed.SavePlan()), int32(FSkinEditor::ESavePlan::Overwrite));
		// Loading the class look over it: everything off.
		Ed.Load(nullptr);
		TestEqual(TEXT("Class look"), int32(Ed.SavePlan()), int32(FSkinEditor::ESavePlan::ClassLook));
		TestTrue(TEXT("Loading is undoable"), Ed.Undo() && Ed.GetDraft().Wear.Level == 0);
		TestEqual(TEXT("Undoing a load brings back the skin loaded before it"), Ed.GetLoadedId(), FString(TEXT("my-navy")));
		TestEqual(TEXT("and Use would write that skin"), int32(Ed.SavePlan()), int32(FSkinEditor::ESavePlan::Overwrite));
		// Picking another skin and undoing it: Use must not write the first look into the second's file.
		Ed.OpenWith(J22, &NavySkin);
		TestFalse(TEXT("The worn skin, unchanged, has nothing to save"), Ed.IsUnsaved());
		Ed.Load(&Mine);
		TestTrue(TEXT("A picked skin is not on the boat until Use"), !Ed.IsDirty() && Ed.IsUnsaved());
		Ed.Undo();
		TestEqual(TEXT("Undo: the built-in again"), Ed.GetLoadedId(), NavySkin.Id);
		TestEqual(TEXT("Undo: nothing to write"), int32(Ed.SavePlan()), int32(FSkinEditor::ESavePlan::Existing));
		TestFalse(TEXT("Undo: nothing to save"), Ed.IsUnsaved());
		// No trim, no cove stripe: said in the file, kept through it, and taken off a class look that has them.
		Ed.OpenWith(J22, nullptr);
		Ed.SetPartOff(FSkinEditor::EPart::Trim);
		Ed.SetPartOff(FSkinEditor::EPart::Cove);
		FBoatSkin Back;
		TestTrue(TEXT("No trim reads back"), FBoatSkin::FromJson(Ed.GetDraft().ToJson(), Back) == FBoatSkin::EResult::Ok
			&& Back.Paint.bTrim.IsSet() && !Back.Paint.bTrim.GetValue() && Back.Paint.bCove.IsSet() && !Back.Paint.bCove.GetValue());
		FBoatLivery Teak = SampleBoatLivery(J22, 0);
		Teak.bTeak = true;
		Teak.bCove = true;
		Back.ApplyTo(Teak, J22);
		TestTrue(TEXT("No trim and no cove on the boat"), !Teak.bTeak && !Teak.bCove && Teak.Cove.Equals(Teak.Hull));
		Ed.SetPartColour(FSkinEditor::EPart::Trim, Red);
		TestFalse(TEXT("A colour puts the trim back"), Ed.IsPartOff(FSkinEditor::EPart::Trim));
		// Every built-in shows its own scheme's trim and stripes over the class's look.
		for (const FBoatSkin& B : BoatSkinStore::BuiltIn(J22))
		{
			FBoatLivery L = SampleBoatLivery(J22, 0);
			B.ApplyTo(L, J22);
			TestEqual(*FString::Printf(TEXT("%s: trim as its paint says"), *B.Id), L.bTeak, B.Paint.bTrim.Get(false));
			TestEqual(*FString::Printf(TEXT("%s: cove as its paint says"), *B.Id), L.bCove, B.Paint.bCove.Get(false));
		}
	}
	// Surprise me: a real scheme's paint, a wear level short of neglected, ropes in range; one undo step.
	FRandomStream Random(1288);
	for (int32 K = 0; K < 50; ++K)
	{
		Ed.OpenWith(J22, nullptr);
		Ed.Surprise(Random);
		const FBoatSkin& D = Ed.GetDraft();
		TestTrue(TEXT("Surprise: a hull colour"), D.Paint.Hull.IsSet());
		TestTrue(TEXT("Surprise: wear short of neglected"), D.Wear.Level >= 0 && D.Wear.Level <= 3);
		for (int32 L = 0; L < int32(FBoatSkin::ELine::Count); ++L) TestTrue(TEXT("Surprise: a colourway"), D.Lines.Column[L] >= 0 && D.Lines.Column[L] < FBoatSkin::NumRopeColourways());
		TestTrue(TEXT("Surprise is one step"), Ed.Undo() && !Ed.CanUndo() && !Ed.IsDirty());
	}
	// The rope names cover the colourways.
	for (int32 C = 0; C < FBoatSkin::NumRopeColourways(); ++C) TestFalse(FString::Printf(TEXT("Colourway %d has a name"), C), FSkinEditor::RopeName(C) == FSkinEditor::RopeName(-1));
	return true;
}

// The Customize screen builds on every tab without a player, its keys work (tabs, Surprise me, undo), and Back with
// changes asks once before it leaves without saving.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSailingSkinScreenTest, "SailingSim.Skin.Screen", SailSkinTestsLocal::SkinFlags)
bool FSailingSkinScreenTest::RunTest(const FString&)
{
	if (!FSlateApplication::IsInitialized()) { AddWarning(TEXT("No Slate application")); return true; }
	auto Key = [](const FKey& K) { return FKeyEvent(K, FModifierKeysState(), 0, false, 0, 0); };
	TSharedRef<SSailFrontEnd> F = SNew(SSailFrontEnd).Start(ESailScreen::Title);
	F->Push(ESailScreen::Boat);
	F->OpenCustomize(int32(Sailing::EBoatType::J22));
	TestTrue(TEXT("Customize opens from the Boat screen"), F->Current() == ESailScreen::Customize);
	TestTrue(TEXT("It has a default focus"), F->FocusTarget().IsValid());
	for (int32 Tab = 0; Tab < 5; ++Tab)
	{
		TestTrue(FString::Printf(TEXT("E moves to the next tab (%d)"), Tab), F->OnKeyDown(FGeometry(), Key(EKeys::E)).IsEventHandled());
		TestTrue(FString::Printf(TEXT("Tab %d builds with a focus"), Tab), F->Current() == ESailScreen::Customize && F->FocusTarget().IsValid());
	}
	TestTrue(TEXT("Q moves back a tab"), F->OnKeyDown(FGeometry(), Key(EKeys::Q)).IsEventHandled());
	TestFalse(TEXT("Clean at the start"), F->GetSkinEditor().IsDirty());
	TestTrue(TEXT("R is Surprise me"), F->OnKeyDown(FGeometry(), Key(EKeys::R)).IsEventHandled());
	TestTrue(TEXT("Surprise me changed the draft"), F->GetSkinEditor().IsDirty());
	// Back with changes: once to be told, again to leave.
	TestTrue(TEXT("Back is taken"), F->OnKeyDown(FGeometry(), Key(EKeys::Escape)).IsEventHandled());
	TestTrue(TEXT("Still on Customize after the first Back"), F->Current() == ESailScreen::Customize);
	TestTrue(TEXT("Z undoes"), F->OnKeyDown(FGeometry(), Key(EKeys::Z)).IsEventHandled());
	TestFalse(TEXT("Clean after the undo"), F->GetSkinEditor().IsDirty());
	TestTrue(TEXT("Y redoes"), F->OnKeyDown(FGeometry(), Key(EKeys::Y)).IsEventHandled());
	TestTrue(TEXT("Dirty after the redo"), F->GetSkinEditor().IsDirty());
	F->OnKeyDown(FGeometry(), Key(EKeys::Escape));
	TestTrue(TEXT("The first Back after a change stays"), F->Current() == ESailScreen::Customize);
	F->OnKeyDown(FGeometry(), Key(EKeys::Escape));
	TestTrue(TEXT("The second Back leaves for the Boat screen"), F->Current() == ESailScreen::Boat);
	// Clean, Back leaves at once.
	F->OpenCustomize(int32(Sailing::EBoatType::Sunfish));
	TestTrue(TEXT("Opens for the Sunfish"), F->Current() == ESailScreen::Customize && F->GetSkinEditor().GetBoatType() == int32(Sailing::EBoatType::Sunfish));
	F->OnKeyDown(FGeometry(), Key(EKeys::Escape));
	TestTrue(TEXT("Back leaves a clean screen at once"), F->Current() == ESailScreen::Boat);
	return true;
}
