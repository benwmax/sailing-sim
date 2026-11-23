// A ship's outside model (docs/frigate-import/): the parts of her export built in the ship's frame, loaded under BoatRoot
// from the table Content/TerrainData/Ships/<Config>.sockets.json and shown by her state. The rig (ShipModelVisuals.cpp)
// then finds the yards and sails among them and moves them; the frames find nothing of theirs here (the wheel and the
// capstan are on their own pivots and stay the frames' to place). Without the table or the hull in the project she is
// drawn from her config as before (-SailingClassicFrigate keeps that for compared stills).
#include "ShipOutside.h"
#include "SailboatPawn.h"
#include "SailingSim.h"
#include "BenchRunner.h"
#include "CannonBattery.h"
#include "SailingSettings.h"
#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/AssetManager.h"
#include "Engine/StaticMesh.h"
#include "Engine/StreamableManager.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace ShipOutside
{
	uint8 StateBit(const FString& Name)
	{
		if (Name == TEXT("underway")) return Underway;
		if (Name == TEXT("action")) return Action;
		if (Name == TEXT("clewed")) return Clewed;
		if (Name == TEXT("anchored")) return Anchored;
		return 0;
	}

	FString TablePath(const FString& ConfigName)
	{
		return FPaths::ProjectContentDir() / TEXT("TerrainData") / TEXT("Ships") / (ConfigName + TEXT(".sockets.json"));
	}

	bool ParseTable(const FString& Json, TArray<FPart>& Out, FString* Error)
	{
		Out.Reset();
		TSharedPtr<FJsonObject> Root;
		if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json), Root) || !Root.IsValid())
		{
			if (Error) *Error = TEXT("not json");
			return false;
		}
		const TSharedPtr<FJsonObject>* Meshes = nullptr;
		if (!Root->TryGetObjectField(TEXT("meshes"), Meshes) || !Meshes || !Meshes->IsValid())
		{
			if (Error) *Error = TEXT("no meshes");
			return false;
		}
		for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : (*Meshes)->Values)
		{
			const TSharedPtr<FJsonObject> M = Pair.Value.IsValid() ? Pair.Value->AsObject() : nullptr;
			if (!M.IsValid()) continue;
			FString Group, Frame, Asset;
			M->TryGetStringField(TEXT("group"), Group);
			M->TryGetStringField(TEXT("frame"), Frame);
			if (Group != TEXT("Outside") || Frame != TEXT("ship")) continue;
			if (!M->TryGetStringField(TEXT("asset"), Asset) || Asset.IsEmpty()) continue;
			FPart P;
			if (!M->TryGetStringField(TEXT("part"), P.Name) || P.Name.IsEmpty())
			{
				int32 Cut = INDEX_NONE;
				P.Name = Pair.Key.FindLastChar(TEXT('_'), Cut) ? Pair.Key.Mid(Cut + 1) : Pair.Key;
			}
			P.Asset = Asset + TEXT(".") + Pair.Key;
			const TSharedPtr<FJsonObject>* Light = nullptr;
			if (M->TryGetObjectField(TEXT("light"), Light) && Light && Light->IsValid()) P.LightAsset = Asset + TEXT("_Light.") + Pair.Key + TEXT("_Light");
			const TArray<TSharedPtr<FJsonValue>>* States = nullptr;
			if (M->TryGetArrayField(TEXT("states"), States) && States)
			{
				P.States = 0;
				for (const TSharedPtr<FJsonValue>& S : *States) P.States |= StateBit(S->AsString());
				if (P.States == 0) P.States = AllStates;   // an unknown word: shown rather than lost
			}
			double Triangles = 0.0;
			if (M->TryGetNumberField(TEXT("triangles"), Triangles)) P.Triangles = int32(Triangles);
			Out.Add(MoveTemp(P));
		}
		Out.Sort([](const FPart& A, const FPart& B) { return A.Name < B.Name; });
		if (Out.Num() == 0 && Error) *Error = TEXT("no outside parts");
		return Out.Num() > 0;
	}

	FString GroupOf(const FString& PartName)
	{
		// Running_<Group>_<Set|Clewed|Furled>, Blocks_<Group>_<Set|Clewed|Furled>
		TArray<FString> Words;
		PartName.ParseIntoArray(Words, TEXT("_"), true);
		if (Words.Num() != 3 || (Words[0] != TEXT("Running") && Words[0] != TEXT("Blocks"))) return FString();
		if (Words[2] != TEXT("Set") && Words[2] != TEXT("Clewed") && Words[2] != TEXT("Furled")) return FString();
		return Words[1];
	}

	FString GroupOfSail(const FString& SailName)
	{
		const FString S = SailName.ToLower();
		if (S == TEXT("jib") || S == TEXT("flying_jib") || S == TEXT("fore_topmast_staysail")) return TEXT("Headsails");
		if (S.Contains(TEXT("staysail"))) return TEXT("Staysails");
		if (S.StartsWith(TEXT("spanker"))) return TEXT("Spanker");
		if (S.StartsWith(TEXT("fore"))) return TEXT("Fore");
		if (S.StartsWith(TEXT("main"))) return TEXT("Main");
		if (S.StartsWith(TEXT("mizzen")) || S.StartsWith(TEXT("crossjack"))) return TEXT("Mizzen");
		if (S.StartsWith(TEXT("spritsail"))) return TEXT("Fore");
		return FString();
	}
}

namespace ShipOutsideGame
{
	/** The folder and mesh prefix of a ship's exported model by her config name (ShipRigGame::ModelFolder's twin). */
	FString ModelFolder(const char* ConfigName)
	{
		const FString Name = UTF8_TO_TCHAR(ConfigName ? ConfigName : "");
		if (Name == TEXT("Commonwealth")) return TEXT("Frigate");
		return Name;
	}

	/** The table of a ship's outside parts, read once per config name (no UObjects: safe in a static). */
	const TArray<ShipOutside::FPart>* TableFor(const char* ConfigName)
	{
		static TMap<FString, TArray<ShipOutside::FPart>> Tables;
		const FString Name = UTF8_TO_TCHAR(ConfigName ? ConfigName : "");
		if (TArray<ShipOutside::FPart>* Known = Tables.Find(Name)) return Known->Num() > 0 ? Known : nullptr;
		TArray<ShipOutside::FPart>& Parts = Tables.Add(Name);
		FString Text, Error;
		const FString Path = ShipOutside::TablePath(Name);
		if (!FFileHelper::LoadFileToString(Text, *Path, FFileHelper::EHashOptions::None, FILEREAD_Silent)) return nullptr;
		if (!ShipOutside::ParseTable(Text, Parts, &Error))
		{
			SAIL_LOG(Warning, TEXT("Ship outside table %s: %s"), *Path, *Error);
			Parts.Reset();
			return nullptr;
		}
		return &Parts;
	}

	/** Whether the twins stand in for the heroes: Low and Medium (the Mac gates' Medium 60), or -SailingFrigateLight=1. */
	bool UseLight()
	{
		int32 Arg = -1;
		if (FParse::Value(SailingArgs::Dev(), TEXT("SailingFrigateLight="), Arg)) return Arg != 0;
		const ESailingQuality Q = USailingSettings::Get()->Quality;
		return Q == ESailingQuality::Low || Q == ESailingQuality::Medium;
	}
}

bool ASailboatPawn::HasShipOutsideModel() const
{
	using namespace Sailing;
	if (!IsSquareRigged(Boat.GetConfig().Type) || FParse::Param(SailingArgs::Dev(), TEXT("SailingClassicFrigate"))) return false;
	const TArray<ShipOutside::FPart>* Table = ShipOutsideGame::TableFor(Boat.GetConfig().Name);
	if (!Table) return false;
	// Her hull: the table alone (committed with the import) is no model; the skin must be in the project.
	const FString Folder = ShipOutsideGame::ModelFolder(Boat.GetConfig().Name);
	return FPackageName::DoesPackageExist(FString::Printf(TEXT("/Game/Boats/%s/Outside/SM_%s_Skin"), *Folder, *Folder));
}

bool ASailboatPawn::ShipOutsideOwns(const FString& PartName) const
{
	return bShipOutsideModel && ShipOutsideNames.Contains(PartName);
}

void ASailboatPawn::ClearShipOutside()
{
	for (UStaticMeshComponent* Mesh : ShipOutsideMeshes) if (Mesh) Mesh->DestroyComponent();
	ShipOutsideMeshes.Reset();
	ShipOutsideParts.Reset();
	ShipOutsideNames.Reset();
	ShipOutsidePending.Reset();
	if (ShipOutsideLoad.IsValid()) ShipOutsideLoad->CancelHandle();
	ShipOutsideLoad.Reset();
	bShipOutsideLoaded = false;
	ShipOutsideStateShown = 0;
}

void ASailboatPawn::BindShipOutside()
{
	ClearShipOutside();
	if (!bShipOutsideModel || !BoatRoot) return;
	const TArray<ShipOutside::FPart>* Table = ShipOutsideGame::TableFor(Boat.GetConfig().Name);
	if (!Table) return;
	const bool bLight = ShipOutsideGame::UseLight();
	for (const ShipOutside::FPart& P : *Table)
	{
		FShipOutsidePart Part;
		Part.Name = P.Name;
		Part.States = P.States;
		Part.Group = ShipOutside::GroupOf(P.Name);
		ShipOutsideParts.Add(Part);
		ShipOutsideNames.Add(P.Name);
		ShipOutsidePending.Add(FSoftObjectPath(bLight && !P.LightAsset.IsEmpty() ? P.LightAsset : P.Asset));
	}
	ShipOutsideLoad = UAssetManager::GetStreamableManager().RequestAsyncLoad(ShipOutsidePending);
	SAIL_LOG(Log, TEXT("Ship outside %s: %d parts to load (%s)"), UTF8_TO_TCHAR(Boat.GetConfig().Name), ShipOutsidePending.Num(),
		bLight ? TEXT("light twins") : TEXT("heroes"));
}

void ASailboatPawn::UpdateShipOutside(float DeltaSeconds)
{
	using namespace Sailing;
	if (!bShipOutsideModel || ShipOutsideParts.Num() == 0) return;

	// The parts, once loaded: in her frame (BoatRoot, no offset), static (the rig makes movable what it moves), drawn and
	// shadowed, no collision. Then the rig and the frames bind again, to find the yards and sails among them.
	if (!bShipOutsideLoaded && ShipOutsideLoad.IsValid() && ShipOutsideLoad->HasLoadCompleted())
	{
		int32 Missing = 0;
		for (int32 K = 0; K < ShipOutsidePending.Num() && K < ShipOutsideParts.Num(); ++K)
		{
			UStaticMesh* Asset = Cast<UStaticMesh>(ShipOutsidePending[K].ResolveObject());
			if (!Asset) { ++Missing; continue; }
			UStaticMeshComponent* Mesh = NewObject<UStaticMeshComponent>(this);
			Mesh->SetupAttachment(BoatRoot.Get());
			Mesh->SetStaticMesh(Asset);
			Mesh->SetMobility(EComponentMobility::Static);
			Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			Mesh->SetCanEverAffectNavigation(false);
			Mesh->RegisterComponent();
			ShipOutsideMeshes.Add(Mesh);
			ShipOutsideParts[K].Mesh = Mesh;
		}
		bShipOutsideLoaded = true;
		ShipOutsideStateShown = 0;
		SAIL_LOG(Log, TEXT("Ship outside %s: %d parts on the boat, %d did not load"), UTF8_TO_TCHAR(Boat.GetConfig().Name),
			ShipOutsideMeshes.Num(), Missing);
		BindShipRig();
		BindShipFrames();
	}
	if (!bShipOutsideLoaded) return;

	// Her state: the guns run out (any gun past loading on its way out or back) is action, else underway; each rig
	// group's running rigging and blocks follow its sails (set while any is set, clewed while any is, else furled).
	bool bAction = false;
	if (ShipBattery)
	{
		for (const FGun& G : ShipBattery->GetBattery().Guns())
		{
			if (G.State == EGunState::OpeningLid || G.State == EGunState::RunningOut || G.State == EGunState::Ready || G.State == EGunState::Lock
				|| G.State == EGunState::Recoil || G.State == EGunState::Spent || G.State == EGunState::RunningIn) { bAction = true; break; }
		}
	}
	const uint8 ShipState = bAction ? ShipOutside::Action : ShipOutside::Underway;
	uint8 GroupStates[8] = {};
	static const TCHAR* Groups[7] = { TEXT("Fore"), TEXT("Main"), TEXT("Mizzen"), TEXT("Spanker"), TEXT("Headsails"), TEXT("Staysails"), TEXT("Spritsail") };
	if (ShipRig)
	{
		for (int32 G = 0; G < 7; ++G)
		{
			const FString Want = Groups[G] == FString(TEXT("Spritsail")) ? TEXT("Fore") : Groups[G];
			bool bAnySet = false, bAnyClewed = false, bAny = false;
			for (int32 K = 0; K < ShipRig->NumSails; ++K)
			{
				if (ShipOutside::GroupOfSail(UTF8_TO_TCHAR(ShipRig->Sails[K].Name)) != Want) continue;
				bAny = true;
				const ESailShown Shown = ShipRigPose.GetShown(K);
				bAnySet |= Shown == ESailShown::Set;
				bAnyClewed |= Shown == ESailShown::Clewed;
			}
			GroupStates[G] = !bAny ? ShipState : (bAnySet ? ShipState : (bAnyClewed ? ShipOutside::Clewed : ShipOutside::Anchored));
		}
	}
	else
	{
		for (int32 G = 0; G < 7; ++G) GroupStates[G] = ShipState;
	}
	// Changed only when a state did (a key of the eight): the rig's own parts (Sail_*) are its to show.
	uint32 Key = ShipState;
	for (int32 G = 0; G < 7; ++G) Key |= uint32(GroupStates[G]) << (4 * (G + 1));
	if (Key == ShipOutsideStateShown) return;
	ShipOutsideStateShown = Key;
	for (const FShipOutsidePart& Part : ShipOutsideParts)
	{
		UStaticMeshComponent* Mesh = Part.Mesh.Get();
		if (!Mesh || Part.States == ShipOutside::AllStates || Part.Name.StartsWith(TEXT("Sail_"))) continue;
		uint8 State = ShipState;
		for (int32 G = 0; G < 7; ++G) if (Part.Group == Groups[G]) { State = GroupStates[G]; break; }
		const bool bShow = (Part.States & State) != 0;
		if (Mesh->IsVisible() != bShow) Mesh->SetVisibility(bShow);
	}
}
