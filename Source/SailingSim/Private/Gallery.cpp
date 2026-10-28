#include "Gallery.h"
#include "SailingGameMode.h"
#include "SailingSettings.h"
#include "SailingSim.h"
#include "UI/SailCatalog.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetRegistry/IAssetRegistry.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"

namespace SailGallery
{
	namespace
	{
		/** The folder table (the only hand-written part): folder, category, default tags. */
		struct FFolderRule
		{
			const TCHAR* Folder;
			const TCHAR* Category;
			const TCHAR* Tag;
		};
		const FFolderRule Rules[] = {
			{ TEXT("/Game/Boats/Kit"), TEXT("Deck hardware"), TEXT("Hero detail") },
			{ TEXT("/Game/World/Houses"), TEXT("Houses & docks"), nullptr },
			{ TEXT("/Game/World/Trees"), TEXT("Trees"), nullptr },
			{ TEXT("/Game/World/Props"), TEXT("Rocks & plants"), nullptr },
			{ TEXT("/Game/World/Navaids"), TEXT("Buoys & marks"), nullptr },
			{ TEXT("/Game/World/Vessels"), TEXT("Other vessels"), nullptr },
			{ TEXT("/Game/World/Landmarks"), TEXT("Landmarks"), nullptr },
			{ TEXT("/Game/World/Vehicles"), TEXT("Cars & trucks"), nullptr },
			{ TEXT("/Game/Crew/Gear"), TEXT("Crew gear"), nullptr },
		};

		/** Display names and descriptions where splitting the asset name isn't enough (optional; add lines freely). */
		struct FNameRule
		{
			const TCHAR* Asset;
			const TCHAR* Name;
			const TCHAR* Description;
		};
		const FNameRule Names[] = {
			{ TEXT("SM_Landmark_NotreDameGarde"), TEXT("Notre-Dame de la Garde"), TEXT("Marseille's basilica on its hill above the Vieux-Port") },
			{ TEXT("SM_CrewPFD"), TEXT("Life jacket"), TEXT("The crew's inflatable vest (Tools/blender/build_crew_gear.py)") },
			{ TEXT("SM_CrewCap"), TEXT("Cap"), TEXT("The crew's cap") },
			{ TEXT("SM_HouseNear_Dock"), TEXT("Private dock"), TEXT("A near-shore house's dock") },
		};

		bool StartsWithFolder(const FString& Path, const TCHAR* Folder)
		{
			return Path == Folder || Path.StartsWith(FString(Folder) + TEXT("/"));
		}

		/** "HornCleat" -> "Horn cleat", "Block29" -> "Block 29", "Buoy_Can" -> "Buoy can". */
		FString SplitWords(const FString& S)
		{
			FString Spaced;
			for (int32 I = 0; I < S.Len(); ++I)
			{
				const TCHAR C = S[I], P = I > 0 ? S[I - 1] : TCHAR(0);
				if (C == TEXT('_')) { Spaced += TEXT(' '); continue; }
				const bool bBreak = I > 0 && P != TEXT('_') && ((FChar::IsUpper(C) && FChar::IsLower(P)) || (FChar::IsDigit(C) && FChar::IsAlpha(P)) || (FChar::IsAlpha(C) && FChar::IsDigit(P)));
				if (bBreak) Spaced += TEXT(' ');
				Spaced += C;
			}
			// Sentence case: the first letter stays, the rest of the words go lower case (acronyms of two or more capitals stay).
			TArray<FString> Words;
			Spaced.ParseIntoArrayWS(Words);
			for (int32 W = 1; W < Words.Num(); ++W)
			{
				const bool bAcronym = Words[W].Len() > 1 && Words[W].ToUpper() == Words[W] && !Words[W].IsNumeric();
				if (!bAcronym) Words[W] = Words[W].ToLower();
			}
			return FString::Join(Words, TEXT(" "));
		}

		bool TwinOf(const FString& Name, FString& OutBase, bool& bLight)
		{
			if (Name.EndsWith(TEXT("_Light"))) { OutBase = Name.LeftChop(6); bLight = true; return true; }
			if (Name.EndsWith(TEXT("_Far"))) { OutBase = Name.LeftChop(4); bLight = false; return true; }
			return false;
		}

		FSoftObjectPath PathOf(const FAssetRef& A) { return FSoftObjectPath(A.PackagePath + TEXT("/") + A.AssetName + TEXT(".") + A.AssetName); }
	}

	const TArray<FString>& Categories()
	{
		static const TArray<FString> C = { TEXT("Boats"), TEXT("Deck hardware"), TEXT("Houses & docks"), TEXT("Trees"), TEXT("Rocks & plants"),
			TEXT("Buoys & marks"), TEXT("Other vessels"), TEXT("Landmarks"), TEXT("Cars & trucks"), TEXT("Crew gear"), TEXT("Other") };
		return C;
	}

	const TArray<FString>& RootFolders()
	{
		static const TArray<FString> R = { TEXT("/Game/Boats"), TEXT("/Game/World"), TEXT("/Game/Crew/Gear") };
		return R;
	}

	bool IsExcluded(const FString& PackagePath)
	{
		// Baked terrain and marina tiles, the far ring's tiles, and the boats' part folders (boats come whole, from the fleet).
		static const TCHAR* Out[] = { TEXT("/Game/World/Baked"), TEXT("/Game/World/Far"), TEXT("/Game/Boats/J22"), TEXT("/Game/Boats/J22Hero"),
			TEXT("/Game/Boats/Sunfish"), TEXT("/Game/Boats/ILCA7"), TEXT("/Game/Boats/Catalina22"), TEXT("/Game/Boats/Catalina30"),
			TEXT("/Game/Boats/Hobie16"), TEXT("/Game/Boats/Corsair880"), TEXT("/Game/Boats/Lagoon42"), TEXT("/Game/Boats/Maxi"),
			TEXT("/Game/Boats/Materials") };
		for (const TCHAR* F : Out) if (StartsWithFolder(PackagePath, F)) return true;
		return false;
	}

	FString CategoryFor(const FString& PackagePath, const FString& AssetName, TArray<FString>& OutTags)
	{
		for (const FFolderRule& R : Rules)
		{
			if (!StartsWithFolder(PackagePath, R.Folder)) continue;
			if (R.Tag) OutTags.AddUnique(R.Tag);
			if (AssetName.StartsWith(TEXT("SM_HouseNear_"))) OutTags.AddUnique(TEXT("Near shore"));
			else if (AssetName.StartsWith(TEXT("SM_House_"))) OutTags.AddUnique(TEXT("Far shore"));
			return R.Category;
		}
		return TEXT("Other");
	}

	FString DisplayName(const FString& AssetName, FString* OutDescription)
	{
		for (const FNameRule& N : Names)
		{
			if (AssetName == N.Asset)
			{
				if (OutDescription) *OutDescription = N.Description;
				return N.Name;
			}
		}
		FString S = AssetName;
		S.RemoveFromStart(TEXT("SM_"));
		for (const TCHAR* Prefix : { TEXT("Kit_"), TEXT("HouseNear_"), TEXT("House_"), TEXT("Landmark_"), TEXT("Vessel_") }) if (S.RemoveFromStart(Prefix)) break;
		// A numbered shape (_0, _1) counts from 1.
		int32 Under = INDEX_NONE;
		if (S.FindLastChar(TEXT('_'), Under) && Under + 1 < S.Len() && S.Mid(Under + 1).IsNumeric())
		{
			S = S.Left(Under) + TEXT(" ") + FString::FromInt(FCString::Atoi(*S.Mid(Under + 1)) + 1);
		}
		return SplitWords(S);
	}

	TArray<FGalleryItem> BuildIndex(const TArray<FAssetRef>& Meshes, int32* OutOther)
	{
		TArray<FGalleryItem> Items;
		TMap<FString, int32> ByBase;   // package path / asset name -> item
		TArray<const FAssetRef*> Twins;
		for (const FAssetRef& A : Meshes)
		{
			if (IsExcluded(A.PackagePath)) continue;
			FString Base;
			bool bLight = false;
			if (TwinOf(A.AssetName, Base, bLight)) { Twins.Add(&A); continue; }
			FGalleryItem I;
			I.Mesh = PathOf(A);
			I.Key = I.Mesh.ToString();
			I.Folder = A.PackagePath;
			I.Category = CategoryFor(A.PackagePath, A.AssetName, I.Tags);
			I.Name = DisplayName(A.AssetName, &I.Description);
			I.bHero = I.Category == TEXT("Deck hardware");
			ByBase.Add(A.PackagePath / A.AssetName, Items.Add(I));
		}
		for (const FAssetRef* T : Twins)
		{
			FString Base;
			bool bLight = false;
			TwinOf(T->AssetName, Base, bLight);
			if (const int32* At = ByBase.Find(T->PackagePath / Base))
			{
				FGalleryItem& I = Items[*At];
				(bLight ? I.Light : I.Far) = PathOf(*T);
				I.Tags.AddUnique(bLight ? TEXT("Has light version") : TEXT("Has far version"));
			}
			else
			{
				// A twin without its base is listed on its own.
				FGalleryItem I;
				I.Mesh = PathOf(*T);
				I.Key = I.Mesh.ToString();
				I.Folder = T->PackagePath;
				I.Category = CategoryFor(T->PackagePath, T->AssetName, I.Tags);
				I.Name = DisplayName(T->AssetName, &I.Description);
				Items.Add(I);
			}
		}
		// The eight boats of the showroom's strip, whole (the stage shows them in G3; their names and words are the fleet's).
		for (const SailCatalog::FBoat& B : SailCatalog::Boats())
		{
			FGalleryItem I;
			I.Key = FString::Printf(TEXT("Boat:%d"), B.Type);
			I.BoatType = B.Type;
			I.Name = B.Name;
			I.Description = B.Description;
			I.Category = TEXT("Boats");
			I.Folder = TEXT("/Game/Boats");
			I.Tags.Add(B.bDinghy ? TEXT("Dinghy") : B.bMultihull ? TEXT("Multihull") : TEXT("Keelboat"));
			if (B.Type == 0) { I.Tags.Add(TEXT("ASA 101")); I.Tags.Add(TEXT("Hero detail")); I.bHero = true; }
			Items.Add(I);
		}
		const TArray<FString>& Order = Categories();
		Items.Sort([&Order](const FGalleryItem& A, const FGalleryItem& B)
		{
			const int32 CA = Order.IndexOfByKey(A.Category), CB = Order.IndexOfByKey(B.Category);
			if (CA != CB) return CA < CB;
			if (A.BoatType != B.BoatType) return A.BoatType < B.BoatType;
			return A.Name < B.Name;
		});
		if (OutOther) *OutOther = Items.FilterByPredicate([](const FGalleryItem& I) { return I.Category == TEXT("Other"); }).Num();
		return Items;
	}

	TArray<FGalleryItem> ScanRegistry()
	{
		IAssetRegistry& Registry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();
		FARFilter Filter;
		Filter.ClassPaths.Add(UStaticMesh::StaticClass()->GetClassPathName());
		for (const FString& F : RootFolders()) Filter.PackagePaths.Add(FName(*F));
		Filter.bRecursivePaths = true;
		TArray<FAssetData> Found;
		Registry.GetAssets(Filter, Found);
		TArray<FAssetRef> Refs;
		for (const FAssetData& D : Found) Refs.Add({ D.PackagePath.ToString(), D.AssetName.ToString() });
		int32 Other = 0;
		TArray<FGalleryItem> Items = BuildIndex(Refs, &Other);
		TSet<FString> Used;
		for (const FGalleryItem& I : Items) Used.Add(I.Category);
		UE_LOG(LogSailing, Display, TEXT("Gallery index: %d assets, %d categories, %d in Other (%d meshes in the registry)"), Items.Num(), Used.Num(), Other, Found.Num());
		return Items;
	}

	bool Matches(const FGalleryItem& Item, const FString& Search, const FString& Category, const TArray<FString>& Tags)
	{
		if (!Category.IsEmpty() && Category != TEXT("All") && Item.Category != Category) return false;
		for (const FString& T : Tags) if (!Item.Tags.Contains(T)) return false;
		TArray<FString> Words;
		Search.ParseIntoArrayWS(Words);
		const FString Hay = (Item.Name + TEXT(" ") + Item.Folder + TEXT(" ") + Item.Category + TEXT(" ") + FString::Join(Item.Tags, TEXT(" ")) + TEXT(" ") + Item.Key).ToLower();
		for (const FString& W : Words) if (!Hay.Contains(W.ToLower())) return false;
		return true;
	}

	const FGalleryItem* Find(const TArray<FGalleryItem>& Items, const FString& KeyOrPath)
	{
		for (const FGalleryItem& I : Items)
		{
			if (I.Key == KeyOrPath || I.Mesh.GetLongPackageName() == KeyOrPath || I.Name == KeyOrPath) return &I;
		}
		return nullptr;
	}

	FGraphicsSnapshot FGraphicsSnapshot::Capture()
	{
		const USailingSettings* S = USailingSettings::Get();
		FGraphicsSnapshot G;
		G.Quality = uint8(S->Quality);
		G.ResolutionScale = S->ResolutionScale;
		G.AntiAliasing = S->AntiAliasing;
		G.ShadowQuality = S->ShadowQuality;
		G.LightingQuality = S->LightingQuality;
		G.ReflectionQuality = S->ReflectionQuality;
		G.CloudQuality = S->CloudQuality;
		G.WaterQuality = S->WaterQuality;
		G.FoliageQuality = S->FoliageQuality;
		G.ViewDistanceQuality = S->ViewDistanceQuality;
		G.MotionBlur = S->MotionBlur;
		G.bCinematicLook = S->bCinematicLook;
		return G;
	}

	bool FGraphicsSnapshot::operator==(const FGraphicsSnapshot& O) const
	{
		return Quality == O.Quality && ResolutionScale == O.ResolutionScale && AntiAliasing == O.AntiAliasing && ShadowQuality == O.ShadowQuality
			&& LightingQuality == O.LightingQuality && ReflectionQuality == O.ReflectionQuality && CloudQuality == O.CloudQuality
			&& WaterQuality == O.WaterQuality && FoliageQuality == O.FoliageQuality && ViewDistanceQuality == O.ViewDistanceQuality
			&& MotionBlur == O.MotionBlur && bCinematicLook == O.bCinematicLook;
	}

	void FGraphicsSnapshot::Restore(UWorld* World, bool bSave) const
	{
		USailingSettings* S = USailingSettings::Get();
		S->Quality = ESailingQuality(Quality);
		S->ResolutionScale = ResolutionScale;
		S->AntiAliasing = AntiAliasing;
		S->ShadowQuality = ShadowQuality;
		S->LightingQuality = LightingQuality;
		S->ReflectionQuality = ReflectionQuality;
		S->CloudQuality = CloudQuality;
		S->WaterQuality = WaterQuality;
		S->FoliageQuality = FoliageQuality;
		S->ViewDistanceQuality = ViewDistanceQuality;
		S->MotionBlur = MotionBlur;
		S->bCinematicLook = bCinematicLook;
		if (bSave) S->Save();
		if (ASailingGameMode* GM = World ? World->GetAuthGameMode<ASailingGameMode>() : nullptr) GM->ApplyQualitySettings();
	}
}
