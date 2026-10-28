#include "UI/SailFrontEnd.h"
#include "UI/SailWidgets.h"
#include "UI/SailUIStyle.h"
#include "UI/SailGraphicsRows.h"
#include "Gallery.h"
#include "GalleryStage.h"
#include "FreeCamera.h"
#include "SailingGameMode.h"
#include "SailingSettings.h"
#include "SailingSim.h"
#include "BenchRunner.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Components/RectLightComponent.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/StreamableManager.h"
#include "Engine/Texture2D.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Engine/AssetManager.h"
#include "Engine/World.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "ImageUtils.h"
#include "Misc/App.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/SecureHash.h"
#include "Rendering/DrawElements.h"
#include "TextureResource.h"
#include "UObject/StrongObjectPtr.h"
#include "Widgets/Input/SEditableText.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SSpacer.h"
#include "Widgets/Layout/SWrapBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SLeafWidget.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"

/**
 * The gallery's thumbnails (Inputs/gallery/brief.md section 8, G2): each mesh rendered once at runtime by a scene capture
 * on a small rig of its own (show-only: the mesh alone, its base colour, so neither the sky nor the light of the moment
 * shows), one a frame in the list's order, cached in memory and in Saved/GalleryThumbs/ keyed by the mesh's path and the
 * build (a new build renders them again).
 */
struct FGalleryThumbs
{
	static constexpr int32 W = 192;
	static constexpr int32 H = 128;
	TStrongObjectPtr<AActor> Rig;
	UStaticMeshComponent* Mesh = nullptr;
	USceneCaptureComponent2D* Capture = nullptr;
	TStrongObjectPtr<UTextureRenderTarget2D> Target;
	TMap<FString, TSharedPtr<FSlateBrush>> Brushes;
	TArray<TStrongObjectPtr<UTexture2D>> Textures;
	TArray<FString> Queue;
	TMap<FString, FSoftObjectPath> Paths;
	TSharedPtr<FStreamableHandle> Load;
	FString Loading;
	int32 Rendered = 0, FromDisk = 0;

	static FString Dir() { return FPaths::ProjectSavedDir() / TEXT("GalleryThumbs"); }
	static FString FileFor(const FString& Path)
	{
		// The path and the build: a rebuilt game renders its thumbnails again (an asset changes only with a build).
		const FString Key = Path + TEXT("|") + FApp::GetBuildDate() + TEXT("|") + FApp::GetBuildVersion();
		return Dir() / (FMD5::HashAnsiString(*Key) + TEXT(".png"));
	}

	const FSlateBrush* BrushFor(const FString& ItemKey) const
	{
		const TSharedPtr<FSlateBrush>* B = Brushes.Find(ItemKey);
		return B ? B->Get() : nullptr;
	}

	void SetBrush(const FString& ItemKey, UTexture2D* Texture)
	{
		TSharedPtr<FSlateBrush> B = MakeShared<FSlateBrush>();
		B->SetResourceObject(Texture);
		B->ImageSize = FVector2D(W, H);
		B->DrawAs = ESlateBrushDrawType::Image;
		Brushes.Add(ItemKey, B);
		Textures.Emplace(Texture);
	}

	/** Every item with a mesh: from disk when cached, else queued to render (in the list's order). */
	void Begin(UWorld* World, const TArray<FGalleryItem>& Items)
	{
		IFileManager::Get().MakeDirectory(*Dir(), true);
		for (const FGalleryItem& I : Items)
		{
			if (!I.Mesh.IsValid() || Brushes.Contains(I.Key)) continue;
			const FString File = FileFor(I.Mesh.ToString());
			if (UTexture2D* T = FPaths::FileExists(File) ? FImageUtils::ImportFileAsTexture2D(File) : nullptr)
			{
				SetBrush(I.Key, T);
				++FromDisk;
				continue;
			}
			Queue.Add(I.Key);
			Paths.Add(I.Key, I.Mesh);
		}
		if (Queue.Num() == 0 || !World) return;
		FActorSpawnParameters P;
		P.ObjectFlags |= RF_Transient;
		P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		// High over the water, out of every view; the capture shows only the mesh.
		APlayerController* PC = World->GetFirstPlayerController();
		const FVector Base = (PC && PC->GetPawn() ? PC->GetPawn()->GetActorLocation() : FVector::ZeroVector) + FVector(0.f, 0.f, 250000.f);
		AActor* A = World->SpawnActor<AActor>(AActor::StaticClass(), FTransform(Base), P);
		if (!A) { Queue.Reset(); return; }
		Rig.Reset(A);
		USceneComponent* Root = NewObject<USceneComponent>(A, TEXT("ThumbRoot"));
		A->SetRootComponent(Root);
		Root->RegisterComponent();
		Root->SetWorldLocation(Base);
		Mesh = NewObject<UStaticMeshComponent>(A, TEXT("ThumbMesh"));
		Mesh->SetupAttachment(Root);
		Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Mesh->SetVisibleInSceneCaptureOnly(true);
		Mesh->RegisterComponent();
		UTextureRenderTarget2D* RT = NewObject<UTextureRenderTarget2D>(GetTransientPackage());
		RT->RenderTargetFormat = RTF_RGBA8_SRGB;
		RT->ClearColor = FLinearColor(0.035f, 0.045f, 0.06f, 1.f);
		RT->InitAutoFormat(W, H);
		RT->UpdateResourceImmediate(true);
		Target.Reset(RT);
		Capture = NewObject<USceneCaptureComponent2D>(A, TEXT("ThumbCapture"));
		Capture->SetupAttachment(Root);
		Capture->bCaptureEveryFrame = false;
		Capture->bCaptureOnMovement = false;
		Capture->PrimitiveRenderMode = ESceneCapturePrimitiveRenderMode::PRM_UseShowOnlyList;
		Capture->ShowOnlyComponents.Add(Mesh);
		// The mesh's own colours, unlit: a lit capture drew the sky and the clouds behind it (they are not primitives a
		// show-only list leaves out) and needed an exposure of its own.
		Capture->CaptureSource = ESceneCaptureSource::SCS_BaseColor;
		Capture->TextureTarget = RT;
		Capture->FOVAngle = 30.f;
		Capture->ShowFlags.SetAtmosphere(false);
		Capture->ShowFlags.SetFog(false);
		Capture->ShowFlags.SetVolumetricFog(false);
		Capture->ShowFlags.SetCloud(false);
		Capture->ShowFlags.SetMotionBlur(false);
		Capture->ShowFlags.SetBloom(false);
		Capture->ShowFlags.SetDepthOfField(false);
		Capture->ShowFlags.SetLensFlares(false);
		Capture->RegisterComponent();
	}

	/** One step a frame: start the next load, or frame, capture and keep the one that landed. */
	void Tick()
	{
		if (!Rig.IsValid() || !Capture) return;
		if (!Load.IsValid())
		{
			if (Queue.Num() == 0) { Finish(); return; }
			Loading = Queue[0];
			Queue.RemoveAt(0);
			Load = UAssetManager::GetStreamableManager().RequestAsyncLoad(Paths.FindRef(Loading));
			if (!Load.IsValid()) Loading.Reset();
			return;
		}
		if (!Load->HasLoadCompleted()) return;
		UStaticMesh* SM = Cast<UStaticMesh>(Paths.FindRef(Loading).ResolveObject());
		if (SM)
		{
			Mesh->SetStaticMesh(SM);
			// The three-quarter view the stage opens on, the bounding sphere filling the frame's height.
			const FBoxSphereBounds B = SM->GetBounds();
			const FVector Centre = Mesh->GetComponentTransform().TransformPosition(B.Origin);
			const float R = FMath::Max(float(B.SphereRadius), 2.f);
			const float D = R / FMath::Sin(FMath::DegreesToRadians(Capture->FOVAngle * 0.5f * H / W)) * 0.8f;   // the sphere is loose about most shapes: a little inside it
			const FRotator View(-20.f, 135.f + 180.f, 0.f);
			Capture->SetWorldLocationAndRotation(Centre - View.Vector() * D, View);
			Capture->CaptureScene();
			// Read back once for the disk cache, and keep a texture of it for the row.
			TArray<FColor> Px;
			if (FTextureRenderTargetResource* Res = Target->GameThread_GetRenderTargetResource(); Res && Res->ReadPixels(Px) && Px.Num() == W * H)
			{
				// Nothing drawn is no colour at all: the panel's raised grey there.
				for (FColor& C : Px) { if (C.R == 0 && C.G == 0 && C.B == 0) C = FColor(38, 48, 62); C.A = 255; }
				TArray64<uint8> Png;
				FImageUtils::PNGCompressImageArray(W, H, TArrayView64<const FColor>(Px.GetData(), Px.Num()), Png);
				const FString File = FileFor(Paths.FindRef(Loading).ToString());
				FFileHelper::SaveArrayToFile(Png, *File);
				if (UTexture2D* T = MakeTexture(Px))
				{
					SetBrush(Loading, T);
					++Rendered;
				}
			}
			Mesh->SetStaticMesh(nullptr);
		}
		Load->ReleaseHandle();
		Load.Reset();
		Loading.Reset();
	}

	/** A transient texture of the pixels (FImageUtils::CreateTexture2D is the editor's only). */
	static UTexture2D* MakeTexture(const TArray<FColor>& Px)
	{
		UTexture2D* T = UTexture2D::CreateTransient(W, H, PF_B8G8R8A8);
		if (!T) return nullptr;
		T->SRGB = true;
		void* Data = T->GetPlatformData()->Mips[0].BulkData.Lock(LOCK_READ_WRITE);
		FMemory::Memcpy(Data, Px.GetData(), Px.Num() * sizeof(FColor));
		T->GetPlatformData()->Mips[0].BulkData.Unlock();
		T->UpdateResource();
		return T;
	}

	void Finish()
	{
		if (!Rig.IsValid()) return;
		UE_LOG(LogSailing, Display, TEXT("Gallery thumbnails: %d rendered, %d from Saved/GalleryThumbs"), Rendered, FromDisk);
		Rig->Destroy();
		Rig.Reset();
		Mesh = nullptr;
		Capture = nullptr;
	}

	~FGalleryThumbs()
	{
		if (Load.IsValid()) Load->CancelHandle();
		if (Rig.IsValid() && IsValid(Rig.Get())) Rig->Destroy();
	}
};

namespace SailGalleryScreen
{
	using namespace SailUI;
	using Prompt = TTuple<FString, FString, FString>;

	const TCHAR* LightName(EGalleryLight L)
	{
		switch (L)
		{
		case EGalleryLight::Noon: return TEXT("Noon on the lake");
		case EGalleryLight::GoldenHour: return TEXT("Golden hour");
		case EGalleryLight::Overcast: return TEXT("Overcast");
		default: return TEXT("Studio");
		}
	}

	const TCHAR* TierName(int32 T)
	{
		static const TCHAR* Names[] = { TEXT("Low"), TEXT("Medium"), TEXT("High"), TEXT("Ultra") };
		return Names[FMath::Clamp(T, 0, 3)];
	}

	/** The saved fold of the two cards (the gallery's own line in GameUserSettings.ini). */
	bool LoadFolded()
	{
		bool b = false;
		if (GConfig) GConfig->GetBool(TEXT("SailingGallery"), TEXT("bCardsFolded"), b, GGameUserSettingsIni);
		return b;
	}

	void SaveFolded(bool b)
	{
		if (!GConfig) return;
		GConfig->SetBool(TEXT("SailingGallery"), TEXT("bCardsFolded"), b, GGameUserSettingsIni);
		GConfig->Flush(false, GGameUserSettingsIni);
	}

	/** A chip: a small selectable button (category, tag, tier, view, detail). */
	TSharedRef<SSailButton> Chip(const FString& Label, TAttribute<bool> bSelected, FSimpleDelegate OnClicked, TAttribute<EVisibility> Shown = EVisibility::Visible)
	{
		TSharedRef<SSailButton> B = SNew(SSailButton).Look(EButtonLook::Chip).IsSelected(bSelected).Padding(FMargin(10.f, 3.f)).OnClicked(OnClicked)
			[ TextAttr(FText::FromString(Label), EType::Label, TAttribute<FSlateColor>::CreateLambda([bSelected]() { return FSlateColor(bSelected.Get(false) ? Ink : Fg); })) ];
		B->SetVisibility(Shown);
		return B;
	}

	/** A card with a header that folds it to one line (Bean, answers 4 and 5: the graphics and technical views hide). */
	TSharedRef<SWidget> FoldCard(const FString& Title, TAttribute<bool> Folded, FSimpleDelegate Toggle, TSharedRef<SWidget> Body, float Width)
	{
		return SNew(SBox).WidthOverride(Width)
		[
			PanelBox(SNew(SVerticalBox)
				+ SVerticalBox::Slot().AutoHeight()
				[
					SNew(SSailButton).Look(EButtonLook::MenuItem).Padding(FMargin(4.f, 2.f)).OnClicked(Toggle)
					[
						SNew(SHorizontalBox)
						+ SHorizontalBox::Slot().FillWidth(1.f)[ SailUI::Text(Title, EType::Eyebrow, Accent) ]
						+ SHorizontalBox::Slot().AutoWidth()[ TextAttr(TAttribute<FText>::CreateLambda([Folded]() { return FText::FromString(Folded.Get(false) ? TEXT("Show") : TEXT("Hide")); }), EType::Label, FSlateColor(Muted)) ]
					]
				]
				+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 6.f, 0.f, 0.f)
				[
					SNew(SBox).Visibility_Lambda([Folded]() { return Folded.Get(false) ? EVisibility::Collapsed : EVisibility::Visible; })[ Body ]
				], FMargin(14.f, 10.f))
		];
	}

	/** Compare tiers: the two captures with a split the mouse drags; labels on either side. */
	class SCompareSplit : public SLeafWidget
	{
	public:
		SLATE_BEGIN_ARGS(SCompareSplit) {}
			SLATE_ARGUMENT(TWeakObjectPtr<AGalleryStage>, Stage)
		SLATE_END_ARGS()
		void Construct(const FArguments& A) { Stage = A._Stage; }
		virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D(64, 64); }
		virtual FReply OnMouseButtonDown(const FGeometry& G, const FPointerEvent& E) override { bDrag = true; Move(G, E); return FReply::Handled().CaptureMouse(SharedThis(this)); }
		virtual FReply OnMouseButtonUp(const FGeometry&, const FPointerEvent&) override { bDrag = false; return FReply::Handled().ReleaseMouseCapture(); }
		virtual FReply OnMouseMove(const FGeometry& G, const FPointerEvent& E) override { if (bDrag) Move(G, E); return bDrag ? FReply::Handled() : FReply::Unhandled(); }
		virtual int32 OnPaint(const FPaintArgs&, const FGeometry& G, const FSlateRect&, FSlateWindowElementList& Out, int32 Layer, const FWidgetStyle&, bool) const override
		{
			const AGalleryStage* S = Stage.Get();
			UTexture2D* TA = S ? S->GetCompareA() : nullptr;
			UTexture2D* TB = S ? S->GetCompareB() : nullptr;
			if (!TA || !TB) return Layer;
			const FVector2f Sz(G.GetLocalSize());
			BrushA.SetResourceObject(TA);
			BrushB.SetResourceObject(TB);
			BrushA.SetUVRegion(FBox2f(FVector2f(0.f, 0.f), FVector2f(Split, 1.f)));
			BrushB.SetUVRegion(FBox2f(FVector2f(Split, 0.f), FVector2f(1.f, 1.f)));
			const float X = Sz.X * Split;
			FSlateDrawElement::MakeBox(Out, Layer, G.ToPaintGeometry(FVector2f(X, Sz.Y), FSlateLayoutTransform()), &BrushA);
			FSlateDrawElement::MakeBox(Out, Layer, G.ToPaintGeometry(FVector2f(Sz.X - X, Sz.Y), FSlateLayoutTransform(FVector2f(X, 0.f))), &BrushB);
			FSlateDrawElement::MakeLines(Out, Layer + 1, G.ToPaintGeometry(), { FVector2f(X, 0.f), FVector2f(X, Sz.Y) }, ESlateDrawEffect::None, FLinearColor::White, true, 2.f);
			return Layer + 1;
		}
	private:
		void Move(const FGeometry& G, const FPointerEvent& E)
		{
			Split = FMath::Clamp(float(G.AbsoluteToLocal(E.GetScreenSpacePosition()).X / FMath::Max(G.GetLocalSize().X, 1.0)), 0.02f, 0.98f);
		}
		TWeakObjectPtr<AGalleryStage> Stage;
		mutable FSlateBrush BrushA, BrushB;
		float Split = 0.5f;
		bool bDrag = false;
	};
}

// ---------------------------------------------------------------- the stage's life

void SSailFrontEnd::OpenGallery()
{
	if (GalleryStage.IsValid() || !Player.IsValid()) return;
	UWorld* World = Player->GetWorld();
	FActorSpawnParameters P;
	P.ObjectFlags |= RF_Transient;
	AGalleryStage* Stage = World ? World->SpawnActor<AGalleryStage>(FVector::ZeroVector, FRotator::ZeroRotator, P) : nullptr;
	if (!Stage) return;
	GalleryStage = Stage;
	Stage->Open(Player.Get());
	// Uncooked (-game from the editor binary) the registry may not have scanned the content yet when the gallery opens
	// with the menus: scan the gallery's folders first, or the list holds only the boats. A cooked game reads its
	// registry whole at startup.
#if WITH_EDITOR
	IAssetRegistry& Registry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();
	if (Registry.IsLoadingAssets()) Registry.WaitForCompletion();
	Registry.ScanPathsSynchronous(SailGallery::RootFolders(), false);
#endif
	GalleryItems = SailGallery::ScanRegistry();
	bGalleryFolded = SailGalleryScreen::LoadFolded();
	bGalleryFull = bGalleryClean = bGalleryViewer = bGalleryMore = bGalleryCompareShown = bGalleryCompareAsked = false;
	GallerySelected = -1;
	GalleryThumbs = MakeShared<FGalleryThumbs>();
	GalleryThumbs->Begin(World, GalleryItems);
	RegisterActiveTimer(0.f, FWidgetActiveTimerDelegate::CreateSP(this, &SSailFrontEnd::TickGallery));
	if (GalleryItems.Num() > 0) SelectGalleryItem(0);
}

void SSailFrontEnd::CloseGallery(bool bRestoreGraphics)
{
	if (AGalleryStage* Stage = GalleryStage.Get())
	{
		if (bRestoreGraphics) Stage->RestoreGraphics();
		Stage->Close();
		Stage->Destroy();
	}
	GalleryStage.Reset();
	GalleryThumbs.Reset();
	GalleryRows.Reset();
	GalleryRowItems.Reset();
}

EActiveTimerReturnType SSailFrontEnd::TickGallery(double, float)
{
	if (!GalleryStage.IsValid()) return EActiveTimerReturnType::Stop;
	if (GalleryThumbs.IsValid()) GalleryThumbs->Tick();
	// The compare split shows once both captures are in.
	if (bGalleryCompareAsked && !GalleryStage->IsComparing() && GalleryStage->GetCompareA() && GalleryStage->GetCompareB())
	{
		bGalleryCompareAsked = false;
		bGalleryCompareShown = true;
	}
	return EActiveTimerReturnType::Continue;
}

void SSailFrontEnd::SelectGalleryItem(int32 Item)
{
	if (!GalleryItems.IsValidIndex(Item) || Item == GallerySelected) return;
	GallerySelected = Item;
	bGalleryCompareShown = false;
	if (AGalleryStage* Stage = GalleryStage.Get())
	{
		// Focus is the selection (the showroom's strip): a flick down the list loads only where it stops (200 ms).
		Stage->Select(GalleryItems[Item]);
		UE_LOG(LogSailing, Display, TEXT("Gallery: %s (%s)"), *GalleryItems[Item].Name, *GalleryItems[Item].Category);
	}
}

void SSailFrontEnd::StepGalleryCategory(int32 Dir)
{
	TArray<FString> Cats = { TEXT("All") };
	for (const FString& C : SailGallery::Categories())
	{
		if (GalleryItems.ContainsByPredicate([&C](const FGalleryItem& I) { return I.Category == C; })) Cats.Add(C);
	}
	const int32 At = FMath::Max(Cats.IndexOfByKey(GalleryCategory), 0);
	GalleryCategory = Cats[(At + Dir + Cats.Num()) % Cats.Num()];
	GalleryTags.Reset();
	RefreshGallery(true);
}

void SSailFrontEnd::FocusGalleryRow()
{
	// The selected row if it is listed, else the first (once laid out: a new row has no path to focus yet).
	RegisterActiveTimer(0.f, FWidgetActiveTimerDelegate::CreateLambda([this](double, float)
	{
		int32 Row = GalleryRowItems.IndexOfByKey(GallerySelected);
		if (Row == INDEX_NONE) Row = 0;
		if (GalleryRows.IsValidIndex(Row) && GalleryRows[Row].IsValid()) FSlateApplication::Get().SetUserFocus(0, GalleryRows[Row], EFocusCause::Navigation);
		return EActiveTimerReturnType::Stop;
	}));
}

// ---------------------------------------------------------------- the list

void SSailFrontEnd::RefreshGallery(bool bFocusFirst)
{
	using namespace SailUI;
	using namespace SailGalleryScreen;
	if (!GalleryList.IsValid()) return;
	// Category chips with their counts under the search and the tags.
	if (GalleryChips.IsValid())
	{
		GalleryChips->ClearChildren();
		TArray<FString> Cats = { TEXT("All") };
		Cats.Append(SailGallery::Categories());
		for (const FString& C : Cats)
		{
			int32 N = 0;
			for (const FGalleryItem& I : GalleryItems) if (SailGallery::Matches(I, GallerySearch, C, GalleryTags)) ++N;
			const bool bAny = C == TEXT("All") || GalleryItems.ContainsByPredicate([&C](const FGalleryItem& I) { return I.Category == C; });
			if (!bAny) continue;
			GalleryChips->AddSlot().Padding(0.f, 0.f, 6.f, 6.f)
			[
				Chip(FString::Printf(TEXT("%s %d"), *C, N), TAttribute<bool>::CreateLambda([this, C]() { return GalleryCategory == C; }),
					FSimpleDelegate::CreateLambda([this, C]() { GalleryCategory = C; GalleryTags.Reset(); RefreshGallery(false); }))
			];
		}
	}
	// Tags of the chosen category (they AND together), the most common first.
	if (GalleryTagChips.IsValid())
	{
		GalleryTagChips->ClearChildren();
		TMap<FString, int32> Count;
		for (const FGalleryItem& I : GalleryItems)
		{
			if (GalleryCategory != TEXT("All") && I.Category != GalleryCategory) continue;
			for (const FString& T : I.Tags) ++Count.FindOrAdd(T);
		}
		Count.ValueSort([](int32 A, int32 B) { return A > B; });
		for (const TPair<FString, int32>& T : Count)
		{
			const FString TagName = T.Key;
			GalleryTagChips->AddSlot().Padding(0.f, 0.f, 6.f, 6.f)
			[
				Chip(TagName, TAttribute<bool>::CreateLambda([this, TagName]() { return GalleryTags.Contains(TagName); }),
					FSimpleDelegate::CreateLambda([this, TagName]() { if (GalleryTags.Contains(TagName)) GalleryTags.Remove(TagName); else GalleryTags.Add(TagName); RefreshGallery(false); }))
			];
		}
	}
	// The list, under a header per category.
	GalleryList->ClearChildren();
	GalleryRows.Reset();
	GalleryRowItems.Reset();
	GalleryMatches = 0;
	FString LastCategory;
	for (int32 Index = 0; Index < GalleryItems.Num(); ++Index)
	{
		const FGalleryItem& It = GalleryItems[Index];
		if (!SailGallery::Matches(It, GallerySearch, GalleryCategory, GalleryTags)) continue;
		++GalleryMatches;
		if (It.Category != LastCategory)
		{
			LastCategory = It.Category;
			GalleryList->AddSlot().Padding(4.f, 10.f, 4.f, 4.f)[ SailUI::Text(It.Category, EType::Eyebrow, Accent) ];
		}
		const FString Key = It.Key;
		TSharedRef<SHorizontalBox> Tags = SNew(SHorizontalBox);
		for (int32 T = 0; T < FMath::Min(It.Tags.Num(), 2); ++T) Tags->AddSlot().AutoWidth().Padding(0.f, 0.f, 8.f, 0.f)[ SailUI::Text(It.Tags[T], EType::Small, Muted) ];
		TSharedRef<SSailButton> Row = SNew(SSailButton).Look(EButtonLook::Card).Padding(FMargin(6.f))
			.IsSelected_Lambda([this, Index]() { return GallerySelected == Index; })
			.OnFocused_Lambda([this, Index]() { bGalleryViewer = false; SelectGalleryItem(Index); })
			.OnClicked_Lambda([this, Index]()
			{
				// Enter or A on a row: the viewer takes the input (the left stick pans); Esc or B comes back.
				SelectGalleryItem(Index);
				bGalleryViewer = true;
				FSlateApplication::Get().SetUserFocus(0, SharedThis(this), EFocusCause::SetDirectly);
			})
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0.f, 0.f, 10.f, 0.f)
				[
					SNew(SBox).WidthOverride(72.f).HeightOverride(48.f)
					[
						SNew(SBorder).Padding(0.f).BorderImage_Lambda([this, Key]() -> const FSlateBrush*
						{
							const FSlateBrush* B = GalleryThumbs.IsValid() ? GalleryThumbs->BrushFor(Key) : nullptr;
							return B ? B : Rounded(Raise, 4.f);
						})
					]
				]
				+ SHorizontalBox::Slot().FillWidth(1.f).VAlign(VAlign_Center)
				[
					SNew(SVerticalBox)
					+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(It.Name, EType::Ui, Fg) ]
					+ SVerticalBox::Slot().AutoHeight()[ Tags ]
				]
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
				[
					It.bHero ? Pill(TEXT("HERO"), true) : SNullWidget::NullWidget
				]
			];
		GalleryList->AddSlot().Padding(0.f, 0.f, 6.f, 4.f)[ Row ];
		GalleryRows.Add(Row);
		GalleryRowItems.Add(Index);
	}
	if (bFocusFirst) FocusGalleryRow();
}

// ---------------------------------------------------------------- the screen

SSailFrontEnd::FEntry SSailFrontEnd::BuildGallery()
{
	using namespace SailUI;
	using namespace SailGalleryScreen;
	FEntry E;
	OpenGallery();
	TWeakObjectPtr<AGalleryStage> Weak = GalleryStage;
	ASailingGameMode* GM = GameMode();
	auto Item = [this]() -> const FGalleryItem* { return GalleryItems.IsValidIndex(GallerySelected) ? &GalleryItems[GallerySelected] : nullptr; };
	auto Panels = [this]() { return bGalleryFull || bGalleryClean ? EVisibility::Collapsed : EVisibility::Visible; };
	auto Chrome = [this]() { return bGalleryClean || bGalleryCompareShown ? EVisibility::Collapsed : EVisibility::Visible; };

	// The left panel: search, categories, tags, the list, the count.
	SAssignNew(GalleryChips, SWrapBox).UseAllottedSize(true);
	SAssignNew(GalleryTagChips, SWrapBox).UseAllottedSize(true);
	SAssignNew(GalleryList, SScrollBox).ScrollBarThickness(FVector2D(4.f, 4.f))
		.ScrollWhenFocusChanges(EScrollWhenFocusChanges::AnimatedScroll).NavigationScrollPadding(40.f);
	TSharedRef<SWidget> Search = SNew(SBorder).BorderImage(Rounded(Raise, RadiusButton, Line, 1.f)).Padding(FMargin(10.f, 6.f))
	[
		SNew(SHorizontalBox)
		+ SHorizontalBox::Slot().FillWidth(1.f).VAlign(VAlign_Center)
		[
			SAssignNew(GallerySearchBox, SEditableText).Text(FText::FromString(GallerySearch)).Font(Font(EType::Ui)).ColorAndOpacity(Fg)
			.HintText(FText::FromString(TEXT("Search (/): live oak, kit cleat")))
			.OnTextChanged_Lambda([this](const FText& T) { GallerySearch = T.ToString(); RefreshGallery(false); })
			.OnTextCommitted_Lambda([this](const FText&, ETextCommit::Type How) { if (How == ETextCommit::OnEnter || How == ETextCommit::OnCleared) FocusGalleryRow(); })
		]
	];
	TSharedRef<SWidget> Left = SNew(SBox).WidthOverride(360.f).Visibility_Lambda(Panels)
	[
		PanelBox(SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(TEXT("Developer"), EType::Eyebrow, Accent) ]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 0.f, 0.f, 10.f)[ SailUI::Text(TEXT("Gallery"), EType::ScreenTitle, Fg) ]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 0.f, 0.f, 10.f)[ Search ]
			+ SVerticalBox::Slot().AutoHeight()[ GalleryChips.ToSharedRef() ]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 2.f, 0.f, 4.f)[ GalleryTagChips.ToSharedRef() ]
			+ SVerticalBox::Slot().FillHeight(1.f)[ GalleryList.ToSharedRef() ]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 8.f, 0.f, 0.f)
			[ TextAttr(TAttribute<FText>::CreateLambda([this]() { return FText::FromString(FString::Printf(TEXT("%d of %d assets"), GalleryMatches, GalleryItems.Num())); }), EType::Small, FSlateColor(Muted)) ],
			FMargin(18.f, 16.f))
	];

	// Over the viewer: the asset's name (44 px) and tags; the light, compare and full screen buttons.
	FSlateFontInfo TitleFont = Font(EType::ScreenTitle);
	TitleFont.Size = 44;
	TSharedRef<SWidget> Title = SNew(SBox).MaxDesiredWidth(760.f)
	[
		SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight()[ TextAttr(TAttribute<FText>::CreateLambda([Item]() { const FGalleryItem* I = Item(); return FText::FromString(I ? I->Category : FString()); }), EType::Eyebrow, FSlateColor(Accent)) ]
		+ SVerticalBox::Slot().AutoHeight()
		[ SNew(STextBlock).Font(TitleFont).ColorAndOpacity(Fg)
			.Text_Lambda([Item]() { const FGalleryItem* I = Item(); return FText::FromString(I ? I->Name.ToUpper() : FString()); }) ]
		+ SVerticalBox::Slot().AutoHeight()[ TextAttr(TAttribute<FText>::CreateLambda([Item]() { const FGalleryItem* I = Item(); return FText::FromString(I ? I->Description : FString()); }), EType::Body, FSlateColor(Muted), true) ]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 6.f, 0.f, 0.f)
		[ TextAttr(TAttribute<FText>::CreateLambda([Item, Weak]()
			{
				const FGalleryItem* I = Item();
				const FString Tags = I ? FString::Join(I->Tags, TEXT("  ·  ")) : FString();
				return FText::FromString(Weak.IsValid() && Weak->IsLoading() ? Tags + TEXT("   Loading…") : Tags);
			}), EType::Label, FSlateColor(Fg)) ]
	];
	auto Button = [](TAttribute<FText> Label, FSimpleDelegate Do)
	{
		return SNew(SSailButton).Look(EButtonLook::Secondary).Padding(FMargin(12.f, 6.f)).OnClicked(Do)[ TextAttr(Label, EType::Label, FSlateColor(Fg)) ];
	};
	TSharedRef<SWidget> Tools = SNew(SHorizontalBox)
		+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 8.f, 0.f)
		[ Button(TAttribute<FText>::CreateLambda([Weak]() { return FText::FromString(FString::Printf(TEXT("Light: %s  (L)"), Weak.IsValid() ? LightName(Weak->GetLight()) : TEXT("-"))); }),
			FSimpleDelegate::CreateLambda([Weak]() { if (Weak.IsValid()) Weak->SetLight(EGalleryLight((uint8(Weak->GetLight()) + 1) % 4)); })) ]
		+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 8.f, 0.f)
		[ Button(TAttribute<FText>::CreateLambda([this, Weak]()
			{
				if (Weak.IsValid() && Weak->IsComparing()) return FText::FromString(TEXT("Comparing…"));
				return FText::FromString(FString::Printf(TEXT("Compare %s / %s  (C)"), TierName(GalleryCompareA), TierName(GalleryCompareB)));
			}),
			FSimpleDelegate::CreateLambda([this, Weak]() { if (Weak.IsValid() && !Weak->IsComparing()) { Weak->StartCompare(GalleryCompareA, GalleryCompareB); bGalleryCompareAsked = true; } })) ]
		+ SHorizontalBox::Slot().AutoWidth()
		[ Button(TAttribute<FText>::CreateLambda([this]() { return FText::FromString(bGalleryFull ? TEXT("Exit full screen  (F)") : TEXT("Full screen  (F)")); }),
			FSimpleDelegate::CreateLambda([this, Weak]() { bGalleryFull = !bGalleryFull; if (Weak.IsValid()) Weak->SetPanelShare(bGalleryFull ? 0.f : 0.25f); })) ];

	// The stats card (folds with the graphics card).
	auto Stat = [Weak](const TCHAR* Label, TFunction<FString(const FGalleryStats&)> Value)
	{
		return SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().FillWidth(1.f)[ SailUI::Text(Label, EType::Small, Muted) ]
			+ SHorizontalBox::Slot().AutoWidth()[ TextAttr(TAttribute<FText>::CreateLambda([Weak, Value]() { return FText::FromString(Weak.IsValid() ? Value(Weak->GetStats()) : FString()); }), EType::Small, FSlateColor(Fg)) ];
	};
	TSharedRef<SWidget> StatsBody = SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight()[ Stat(TEXT("Triangles"), [](const FGalleryStats& S) { return FText::AsNumber(S.Triangles).ToString() + (S.bNanite ? TEXT(" (Nanite)") : TEXT("")); }) ]
		+ SVerticalBox::Slot().AutoHeight()[ Stat(TEXT("Detail shown"), [](const FGalleryStats& S) { return S.bNanite ? FString(TEXT("Nanite")) : FString::Printf(TEXT("LOD %d of %d"), S.ShownLod, S.Lods); }) ]
		+ SVerticalBox::Slot().AutoHeight()[ Stat(TEXT("Materials"), [](const FGalleryStats& S) { return FString::FromInt(S.Materials); }) ]
		+ SVerticalBox::Slot().AutoHeight()[ Stat(TEXT("Size"), [](const FGalleryStats& S) { return FString::Printf(TEXT("%.2f x %.2f x %.2f m"), S.SizeM.X, S.SizeM.Y, S.SizeM.Z); }) ]
		+ SVerticalBox::Slot().AutoHeight()[ Stat(TEXT("Render scale"), [](const FGalleryStats& S) { return FString::Printf(TEXT("%.0f%%"), S.ScreenPercentage); }) ]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 6.f, 0.f, 0.f)
		[ TextAttr(TAttribute<FText>::CreateLambda([Weak]() { return FText::FromString(Weak.IsValid() ? Weak->GetStats().Path : FString()); }), EType::Small, FSlateColor(Dim), true) ];
	auto Folded = TAttribute<bool>::CreateLambda([this]() { return bGalleryFolded; });
	auto Fold = FSimpleDelegate::CreateLambda([this]() { bGalleryFolded = !bGalleryFolded; SaveFolded(bGalleryFolded); });
	TSharedRef<SWidget> Stats = SNew(SBox).Visibility_Lambda(Panels)[ FoldCard(TEXT("Model stats"), Folded, Fold, StatsBody, 300.f) ];

	// Graphics & view: the tier, More (the main Settings rows, shared), the view and the detail.
	TSharedRef<SHorizontalBox> Tiers = SNew(SHorizontalBox);
	for (int32 T = 0; T < 4; ++T)
	{
		Tiers->AddSlot().AutoWidth().Padding(0.f, 0.f, 6.f, 0.f)
		[
			Chip(TierName(T), TAttribute<bool>::CreateLambda([T]() { return int32(USailingSettings::Get()->Quality) == T; }),
				FSimpleDelegate::CreateLambda([GM, T]()
				{
					USailingSettings* S = USailingSettings::Get();
					S->Quality = ESailingQuality(T);
					S->ResetGraphicsRows();
					S->Save();
					if (GM) GM->ApplyQualitySettings();
				}))
		];
	}
	auto ViewChip = [Weak](const TCHAR* Label, EGalleryView V)
	{
		return Chip(Label, TAttribute<bool>::CreateLambda([Weak, V]() { return Weak.IsValid() && Weak->GetView() == V; }),
			FSimpleDelegate::CreateLambda([Weak, V]() { if (Weak.IsValid()) Weak->SetView(V); }));
	};
	auto DetailChip = [Weak, Item](const FString& Label, EGalleryDetail D, int32 Lod, TFunction<bool(const FGalleryItem&, const FGalleryStats&)> Offered)
	{
		return Chip(Label, TAttribute<bool>::CreateLambda([Weak, D, Lod]() { return Weak.IsValid() && Weak->GetDetail() == D && (D != EGalleryDetail::Lod || Weak->GetStats().ShownLod == Lod); }),
			FSimpleDelegate::CreateLambda([Weak, D, Lod]() { if (Weak.IsValid()) Weak->SetDetail(D, Lod); }),
			TAttribute<EVisibility>::CreateLambda([Weak, Item, Offered]()
			{
				const FGalleryItem* I = Item();
				return I && Weak.IsValid() && Offered(*I, Weak->GetStats()) ? EVisibility::Visible : EVisibility::Collapsed;
			}));
	};
	TSharedRef<SWrapBox> Details = SNew(SWrapBox).UseAllottedSize(true);
	auto AddDetail = [&](TSharedRef<SWidget> W) { Details->AddSlot().Padding(0.f, 0.f, 6.f, 6.f)[ W ]; };
	AddDetail(DetailChip(TEXT("Auto"), EGalleryDetail::Auto, 0, [](const FGalleryItem&, const FGalleryStats&) { return true; }));
	for (int32 L = 0; L < 4; ++L)
	{
		AddDetail(DetailChip(FString::Printf(TEXT("LOD %d"), L), EGalleryDetail::Lod, L, [L](const FGalleryItem&, const FGalleryStats& S) { return !S.bNanite && S.Lods > 1 && L < S.Lods; }));
	}
	AddDetail(DetailChip(TEXT("Fallback mesh"), EGalleryDetail::Fallback, 0, [](const FGalleryItem&, const FGalleryStats& S) { return S.bNanite; }));
	AddDetail(DetailChip(TEXT("Light (AI boats)"), EGalleryDetail::LightTwin, 0, [](const FGalleryItem& I, const FGalleryStats&) { return I.Light.IsValid(); }));
	AddDetail(DetailChip(TEXT("Far"), EGalleryDetail::FarTwin, 0, [](const FGalleryItem& I, const FGalleryStats&) { return I.Far.IsValid(); }));
	auto Labelled = [](const TCHAR* Label, TSharedRef<SWidget> W)
	{
		return SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 6.f, 0.f, 4.f)[ SailUI::Text(Label, EType::Small, Muted) ]
			+ SVerticalBox::Slot().AutoHeight()[ W ];
	};
	TSharedRef<SVerticalBox> More = SNew(SVerticalBox).Visibility_Lambda([this]() { return bGalleryMore ? EVisibility::Visible : EVisibility::Collapsed; });
	auto AddMore = [&](TSharedRef<SWidget> W) { More->AddSlot().AutoHeight().Padding(0.f, 0.f, 0.f, 6.f)[ W ]; };
	AddMore(SailGraphicsRows::Detail(GM, TEXT("Shadows"), &USailingSettings::ShadowQuality, TEXT("")));
	AddMore(SailGraphicsRows::Detail(GM, TEXT("Lighting"), &USailingSettings::LightingQuality, TEXT("")));
	AddMore(SailGraphicsRows::Detail(GM, TEXT("Reflections"), &USailingSettings::ReflectionQuality, TEXT("")));
	AddMore(SailGraphicsRows::AntiAliasing(GM, false));
	AddMore(SailGraphicsRows::RenderScale(GM, false));
	AddMore(SailGraphicsRows::MotionBlur(GM));
	AddMore(SNew(SSailChoice).Label(TEXT("Compare left")).Options({ TEXT("Low"), TEXT("Medium"), TEXT("High"), TEXT("Ultra") })
		.Index_Lambda([this]() { return int32(GalleryCompareA); }).OnChanged_Lambda([this](int32 I) { GalleryCompareA = uint8(I); }));
	AddMore(SNew(SSailChoice).Label(TEXT("Compare right")).Options({ TEXT("Low"), TEXT("Medium"), TEXT("High"), TEXT("Ultra") })
		.Index_Lambda([this]() { return int32(GalleryCompareB); }).OnChanged_Lambda([this](int32 I) { GalleryCompareB = uint8(I); }));
	AddMore(SNew(SSailButton).Look(EButtonLook::Secondary).Padding(FMargin(12.f, 6.f))
		.IsEnabled_Lambda([Weak]() { return Weak.IsValid() && Weak->GraphicsChanged(); })
		.OnClicked_Lambda([Weak]() { if (Weak.IsValid()) Weak->RestoreGraphics(); })
		[ SailUI::Text(TEXT("Restore my settings"), EType::Label, Fg) ]);
	TSharedRef<SWidget> GraphicsBody = SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight()[ Labelled(TEXT("Tier  (G)"), Tiers) ]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 6.f, 0.f, 0.f)
		[
			SNew(SSailButton).Look(EButtonLook::MenuItem).Padding(FMargin(4.f, 2.f)).OnClicked_Lambda([this]() { bGalleryMore = !bGalleryMore; })
			[ TextAttr(TAttribute<FText>::CreateLambda([this]() { return FText::FromString(bGalleryMore ? TEXT("Fewer settings") : TEXT("More settings")); }), EType::Label, FSlateColor(Fg)) ]
		]
		+ SVerticalBox::Slot().AutoHeight()[ More ]
		+ SVerticalBox::Slot().AutoHeight()
		[ Labelled(TEXT("View"), SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 6.f, 0.f)[ ViewChip(TEXT("Lit"), EGalleryView::Lit) ]
			+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 6.f, 0.f)[ ViewChip(TEXT("Wireframe"), EGalleryView::Wireframe) ]
			+ SHorizontalBox::Slot().AutoWidth()[ ViewChip(TEXT("Lit + wire"), EGalleryView::LitWire) ]) ]
		+ SVerticalBox::Slot().AutoHeight()[ Labelled(TEXT("Detail"), Details) ];
	TSharedRef<SWidget> Graphics = SNew(SBox).Visibility_Lambda(Chrome)[ FoldCard(TEXT("Graphics & view"), Folded, Fold, GraphicsBody, 420.f) ];

	// Orbit controls for the mouse and the readout.
	TSharedRef<SWidget> Orbit = SNew(SBox).Visibility_Lambda(Chrome)
	[
		PanelBox(SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 6.f, 0.f)[ Button(FText::FromString(TEXT("← 45°")), FSimpleDelegate::CreateLambda([Weak]() { if (Weak.IsValid()) Weak->Orbit(FVector2D(-45.0, 0.0)); })) ]
				+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 6.f, 0.f)[ Button(FText::FromString(TEXT("45° →")), FSimpleDelegate::CreateLambda([Weak]() { if (Weak.IsValid()) Weak->Orbit(FVector2D(45.0, 0.0)); })) ]
				+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 6.f, 0.f)[ Button(FText::FromString(TEXT("Zoom out")), FSimpleDelegate::CreateLambda([Weak]() { if (Weak.IsValid()) Weak->Zoom(-2.f); })) ]
				+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 6.f, 0.f)[ Button(FText::FromString(TEXT("Zoom in")), FSimpleDelegate::CreateLambda([Weak]() { if (Weak.IsValid()) Weak->Zoom(2.f); })) ]
				+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 6.f, 0.f)
				[ Button(TAttribute<FText>::CreateLambda([Weak]() { return FText::FromString(Weak.IsValid() && Weak->GetAutoSpin() ? TEXT("Auto spin: on") : TEXT("Auto spin: off")); }),
					FSimpleDelegate::CreateLambda([Weak]() { if (Weak.IsValid()) Weak->SetAutoSpin(!Weak->GetAutoSpin()); })) ]
				+ SHorizontalBox::Slot().AutoWidth()[ Button(FText::FromString(TEXT("Reset  (R)")), FSimpleDelegate::CreateLambda([Weak]() { if (Weak.IsValid()) Weak->ResetView(); })) ]
			]
			+ SVerticalBox::Slot().AutoHeight().Padding(2.f, 6.f, 0.f, 0.f)
			[ TextAttr(TAttribute<FText>::CreateLambda([Weak]()
				{
					const AFreeCamera* C = Weak.IsValid() ? Weak->GetCamera() : nullptr;
					if (!C) return FText::GetEmpty();
					const float Yaw = FMath::Fmod(C->GetActorRotation().Yaw - 135.f - 180.f + 720.f, 360.f);
					return FText::FromString(FString::Printf(TEXT("Angle %.0f°, %.0f° up    Zoom %.2fx"), Yaw, -C->GetActorRotation().Pitch, Weak->GetZoom()));
				}), EType::Small, FSlateColor(Muted)) ], FMargin(12.f, 10.f))
	];

	// Compare: the split over the whole screen (the captures are full frames), labelled with the chosen tiers.
	TSharedRef<SWidget> Compare = SNew(SOverlay).Visibility_Lambda([this]() { return bGalleryCompareShown ? EVisibility::Visible : EVisibility::Collapsed; })
		+ SOverlay::Slot()[ SNew(SCompareSplit).Stage(Weak) ]
		+ SOverlay::Slot().HAlign(HAlign_Left).VAlign(VAlign_Top).Padding(SafeX, SafeTop)
		[ SNew(SBorder).BorderImage(Rounded(Accent, 11.f)).Padding(FMargin(10.f, 3.f))[ TextAttr(TAttribute<FText>::CreateLambda([this]() { return FText::FromString(FString(TierName(GalleryCompareA)).ToUpper()); }), EType::Label, FSlateColor(AccentInk)) ] ]
		+ SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Top).Padding(SafeX, SafeTop)
		[ SNew(SBorder).BorderImage(Rounded(Accent, 11.f)).Padding(FMargin(10.f, 3.f))[ TextAttr(TAttribute<FText>::CreateLambda([this]() { return FText::FromString(FString(TierName(GalleryCompareB)).ToUpper()); }), EType::Label, FSlateColor(AccentInk)) ] ]
		+ SOverlay::Slot().HAlign(HAlign_Center).VAlign(VAlign_Bottom).Padding(0.f, 0.f, 0.f, 90.f)
		[ PanelBox(SailUI::Text(TEXT("Drag the split. Esc, B or any orbit leaves the compare."), EType::Small, Fg), FMargin(12.f, 6.f)) ];

	const float LeftX = 360.f + 30.f;
	E.Content = SNew(SOverlay)
		+ SOverlay::Slot().HAlign(HAlign_Left).Padding(0.f, 0.f, 0.f, 80.f)[ Left ]
		+ SOverlay::Slot().HAlign(HAlign_Left).VAlign(VAlign_Top).Padding(TAttribute<FMargin>::CreateLambda([this, LeftX]() { return FMargin(bGalleryFull ? 0.f : LeftX, 0.f, 0.f, 0.f); }))
		[ SNew(SBox).Visibility_Lambda(Chrome)[ Title ] ]
		+ SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Top)[ SNew(SBox).Visibility_Lambda(Chrome)[ Tools ] ]
		+ SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Top).Padding(0.f, 56.f, 0.f, 0.f)[ Stats ]
		+ SOverlay::Slot().HAlign(HAlign_Left).VAlign(VAlign_Bottom).Padding(TAttribute<FMargin>::CreateLambda([this, LeftX]() { return FMargin(bGalleryFull ? 0.f : LeftX, 0.f, 0.f, 80.f); }))[ Orbit ]
		+ SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Bottom).Padding(0.f, 0.f, 0.f, 80.f)[ Graphics ]
		// The compare split takes the whole screen (out past the body's safe margins).
		+ SOverlay::Slot().Padding(-SafeX, -SafeTop, -SafeX, 0.f)[ Compare ];
	E.Footer = PromptBar({ Prompt(TEXT("↑ ↓"), TEXT("D-pad"), TEXT("Browse")), Prompt(TEXT("Q / E"), TEXT("LB / RB"), TEXT("Category")),
		Prompt(TEXT("Drag"), TEXT("R stick"), TEXT("Orbit")), Prompt(TEXT("Wheel"), TEXT("LT / RT"), TEXT("Zoom")), Prompt(TEXT("G"), TEXT("Y"), TEXT("Tier")),
		Prompt(TEXT("C"), TEXT("X"), TEXT("Compare")), Prompt(TEXT("F"), TEXT("View"), TEXT("Full screen")), Prompt(TEXT("T"), TEXT("L3"), TEXT("Cards")),
		Prompt(TEXT("Esc"), TEXT("B"), TEXT("Back")) }, TEXT("Right drag or Shift: pan"));
	RefreshGallery(false);
	const int32 Row = FMath::Max(GalleryRowItems.IndexOfByKey(GallerySelected), 0);
	if (GalleryRows.IsValidIndex(Row)) E.Focus = GalleryRows[Row];
	return E;
}

// ---------------------------------------------------------------- keys

FReply SSailFrontEnd::GalleryKeyDown(const FKeyEvent& E)
{
	using namespace SailUI;
	AGalleryStage* Stage = GalleryStage.Get();
	if (!Stage) return FReply::Unhandled();
	const FKey K = E.GetKey();
	if (GallerySearchBox.IsValid() && GallerySearchBox->HasKeyboardFocus())
	{
		if (K == EKeys::Escape || K == EKeys::Down || K == EKeys::Gamepad_FaceButton_Right) { FocusGalleryRow(); return FReply::Handled(); }
		return FReply::Unhandled();
	}
	auto Tier = [this](int32 Dir)
	{
		USailingSettings* S = USailingSettings::Get();
		S->Quality = ESailingQuality((int32(S->Quality) + Dir + 4) % 4);
		S->ResetGraphicsRows();
		S->Save();
		if (ASailingGameMode* GM = GameMode()) GM->ApplyQualitySettings();
	};
	if (K == EKeys::F || K == EKeys::Gamepad_Special_Left)
	{
		// Full screen, then (View again, or H) the clean view; F steps back out.
		if (bGalleryClean) bGalleryClean = false;
		else if (bGalleryFull && K == EKeys::Gamepad_Special_Left) bGalleryClean = true;
		else bGalleryFull = !bGalleryFull;
		Stage->SetPanelShare(bGalleryFull || bGalleryClean ? 0.f : 0.25f);
		return FReply::Handled();
	}
	if (K == EKeys::H) { bGalleryClean = !bGalleryClean; if (bGalleryClean) bGalleryFull = true; Stage->SetPanelShare(bGalleryFull ? 0.f : 0.25f); return FReply::Handled(); }
	if (K == EKeys::Q || K == EKeys::Gamepad_LeftShoulder) { StepGalleryCategory(-1); return FReply::Handled(); }
	if (K == EKeys::E || K == EKeys::Gamepad_RightShoulder) { StepGalleryCategory(1); return FReply::Handled(); }
	if (K == EKeys::Slash) { if (GallerySearchBox.IsValid()) FSlateApplication::Get().SetUserFocus(0, GallerySearchBox, EFocusCause::SetDirectly); return FReply::Handled(); }
	if (K == EKeys::R || K == EKeys::Gamepad_RightThumbstick) { Stage->ResetView(); return FReply::Handled(); }
	if (K == EKeys::G || K == EKeys::Gamepad_FaceButton_Top) { Tier(1); return FReply::Handled(); }
	if (K == EKeys::C || K == EKeys::Gamepad_FaceButton_Left)
	{
		if (bGalleryCompareShown) bGalleryCompareShown = false;
		else if (!Stage->IsComparing()) { Stage->StartCompare(GalleryCompareA, GalleryCompareB); bGalleryCompareAsked = true; }
		return FReply::Handled();
	}
	if (K == EKeys::L || K == EKeys::Gamepad_DPad_Left || K == EKeys::Gamepad_DPad_Right || (bGalleryViewer && (K == EKeys::Left || K == EKeys::Right)))
	{
		const int32 Dir = (K == EKeys::Gamepad_DPad_Left || K == EKeys::Left) ? 3 : 1;
		Stage->SetLight(EGalleryLight((uint8(Stage->GetLight()) + Dir) % 4));
		return FReply::Handled();
	}
	if (K == EKeys::T || K == EKeys::Gamepad_LeftThumbstick) { bGalleryFolded = !bGalleryFolded; SailGalleryScreen::SaveFolded(bGalleryFolded); return FReply::Handled(); }
	if (K == EKeys::V) { Stage->SetView(EGalleryView((uint8(Stage->GetView()) + 1) % 3)); return FReply::Handled(); }
	if (bGalleryViewer && (K == EKeys::Up || K == EKeys::Down))
	{
		// The viewer focused: the arrows pan up and down a tenth of the asset.
		Stage->Pan(FVector2D(0.0, (K == EKeys::Up ? 1.0 : -1.0) * Stage->GetStats().SizeM.Size() * 10.0));
		return FReply::Handled();
	}
	if (IsBackKey(K)) { GalleryBack(); return FReply::Handled(); }
	return FReply::Unhandled();
}

void SSailFrontEnd::GalleryBack()
{
	AGalleryStage* Stage = GalleryStage.Get();
	if (bGalleryCompareShown) { bGalleryCompareShown = false; return; }
	if (bGalleryClean) { bGalleryClean = false; return; }
	if (bGalleryFull) { bGalleryFull = false; if (Stage) Stage->SetPanelShare(0.25f); return; }
	if (bGalleryViewer) { bGalleryViewer = false; FocusGalleryRow(); return; }
	auto Leave = [this](bool bRestore)
	{
		CloseGallery(bRestore);
		if (Stack.Num() > 1 && IsGallery())
		{
			Stack.Pop();
			const ESailScreen S = Stack.Last().Screen;
			Stack.Last() = Build(S);
			Show(Stack.Last(), false);
		}
	};
	// Graphics changed in here: keep them or put them back (Restore has the focus, so a look at Ultra on a laptop doesn't stick).
	if (Stage && Stage->GraphicsChanged())
	{
		Confirm(TEXT("Keep these graphics settings?"), TEXT("Keep"), [Leave]() { Leave(false); }, TEXT("Restore"), [Leave]() { Leave(true); });
		return;
	}
	Leave(false);
}
