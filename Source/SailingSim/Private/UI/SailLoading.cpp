#include "UI/SailLoading.h"
#include "SailingSettings.h"
#include "UI/SailWidgets.h"
#include "UI/SailCatalog.h"
#include "SailSession.h"
#include "SailboatPawn.h"
#include "SailingEnvironment.h"
#include "LakeTerrainActor.h"
#include "SailingGameMode.h"
#include "TrafficManager.h"
#include "Drills.h"
#include "EngineUtils.h"
#include "Engine/Texture2D.h"
#include "ShaderPipelineCache.h"
#include "Framework/Application/SlateApplication.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScaleBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"

namespace
{
	struct FTip { const TCHAR* Heading; const TCHAR* Body; };
	// Seeded from the ASA 101 study topics (ui-spec.md 5.7).
	const FTip Tips[] = {
		{ TEXT("Points of sail"), TEXT("Close-hauled, close reach, beam reach, broad reach, run: the closer to the wind, the tighter the sails. Ease until the luff just starts to flutter, then trim back a touch.") },
		{ TEXT("The no-go zone"), TEXT("About 45 degrees either side of the wind, no sail will drive the boat. To get upwind, tack back and forth across it.") },
		{ TEXT("Right of way"), TEXT("Port tack keeps clear of starboard tack. On the same tack, the windward boat keeps clear. An overtaking boat keeps clear of the one ahead.") },
		{ TEXT("Leaving a slip"), TEXT("Plan your exit before you cast off: which lines go first, where the wind will push the bow, and where you'll have room to turn.") },
		{ TEXT("Heaving to"), TEXT("Tack without releasing the jib, then put the tiller to leeward: the boat settles, nearly stopped, with the jib backed. A way to take a break or reef.") },
		{ TEXT("Crew overboard"), TEXT("Shout, point and keep pointing, throw something that floats. Then the quick-stop: turn head to wind at once and circle back under control.") },
		{ TEXT("Reefing"), TEXT("Reef when you first think of it. A smaller main keeps the boat on its feet in gusts and the helm light.") },
		{ TEXT("Reading gusts"), TEXT("Dark patches on the water upwind are gusts on the way. Ease the main as one hits, then trim back as the boat comes up to speed.") },
		{ TEXT("Thunderstorms on Texas lakes"), TEXT("A dark shelf cloud and a sudden cool outflow mean a gust front: reef early, head for shelter, and stay off the water once you hear thunder.") },
	};
}

void SSailLoading::Construct(const FArguments& A)
{
	using namespace SailUI;
	World = A._World;
	OnStart = A._OnStart;
	// Settings > Gameplay > Start automatically when loaded.
	if (USailingSettings::Get()->bAutoStart)
	{
		RegisterActiveTimer(0.25f, FWidgetActiveTimerDelegate::CreateLambda([this](double, float)
		{
			if (!IsReady()) return EActiveTimerReturnType::Continue;
			OnStart.ExecuteIfBound();
			return EActiveTimerReturnType::Stop;
		}));
	}
	RegisterInputTracker();
	ShownAt = FPlatformTime::Seconds();
	const USailSessionSubsystem* Session = World.IsValid() ? USailSessionSubsystem::Get(World.Get()) : nullptr;
	const FSailSessionConfig C = Session && Session->bHasActive ? Session->Active : USailSessionSubsystem::MakeDefault();
	const SailCatalog::FWorld& W = SailCatalog::World(C.World);
	Tip = int32(FMath::Rand() % UE_ARRAY_COUNT(Tips));
	UTexture2D* Tex = W.LoadingTextures.Num() ? SailUI::KeptTexture(W.LoadingTextures[FMath::Rand() % W.LoadingTextures.Num()]) : nullptr;
	Image = MakeShared<FSlateBrush>();
	if (Tex) { Image->SetResourceObject(Tex); Image->ImageSize = FVector2D(Tex->GetSizeX(), Tex->GetSizeY()); }
	else Image->TintColor = FSlateColor(Ink);
	const FString Spot = W.Spots.IsValidIndex(C.LaunchSpot) ? W.Spots[C.LaunchSpot].Name : FString();
	const FString Second = C.Mode == ESailMode::Drill ? FString(DrillName(ESailingDrill(C.DrillIndex + 1))) : USailSessionSubsystem::ModeName(C.Mode);
	const FSailConditions& K = C.Conditions;
	const FString Sub = FString::Printf(TEXT("%.0f kn %s gusting %.0f · %s · %s %d, %s · %s mode"), K.WindKn, *USailSessionSubsystem::CompassPoint(K.WindFromDeg), K.GustKn,
		*USailSessionSubsystem::SkyName(K.Sky), *SailCatalog::MonthName(K.Month), K.Day, *SailCatalog::ClockText(K.LocalHour), C.bLearningMode ? TEXT("Learning") : TEXT("Game"));
	FSlateFontInfo Big = Font(EType::Logo);
	Big.Size = 80.f * 0.75f;
	ChildSlot
	[
		SNew(SOverlay)
		+ SOverlay::Slot()[ SNew(SBorder).BorderImage(White()).BorderBackgroundColor(Ink) ]
		+ SOverlay::Slot()[ SNew(SScaleBox).Stretch(EStretch::ScaleToFill)[ SNew(SImage).Image(Image.Get()) ] ]
		+ SOverlay::Slot()[ SNew(SBorder).BorderImage(White()).BorderBackgroundColor(Ink.CopyWithNewOpacity(0.35f)) ]
		+ SOverlay::Slot().HAlign(HAlign_Left).VAlign(VAlign_Bottom).Padding(FMargin(SafeX, 0.f, 0.f, 120.f))
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(W.Name + TEXT(" · ") + Spot, EType::Eyebrow, Accent) ]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 6.f)[ SNew(STextBlock).Text(FText::FromString((SailCatalog::Boat(C.Boat).Name + TEXT("\n") + Second).ToUpper())).Font(Big).ColorAndOpacity(Fg) ]
			+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(Sub, EType::Body, Fg) ]
		]
		+ SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Center).Padding(FMargin(0.f, 0.f, SafeX, 0.f))
		[
			SNew(SBox).WidthOverride(440.f)
			[
				PanelBox(SNew(SVerticalBox)
					+ SVerticalBox::Slot().AutoHeight()[ TextAttr(TAttribute<FText>::CreateLambda([this]() { return FText::FromString(FString::Printf(TEXT("SAILING TIP · %d OF %d"), Tip + 1, int32(UE_ARRAY_COUNT(Tips)))); }), EType::Eyebrow, FSlateColor(Accent)) ]
					+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 8.f)[ TextAttr(TAttribute<FText>::CreateLambda([this]() { return FText::FromString(FString(Tips[Tip].Heading).ToUpper()); }), EType::CardTitleS, FSlateColor(Fg)) ]
					+ SVerticalBox::Slot().AutoHeight()[ TextAttr(TAttribute<FText>::CreateLambda([this]() { return FText::FromString(Tips[Tip].Body); }), EType::Body, FSlateColor(Muted), true) ]
					+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 14.f, 0.f, 0.f)
					[
						SNew(SHorizontalBox)
						+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 8.f, 0.f)[ KeyCap(TEXT("I"), TEXT("X")) ]
						+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)[ SailUI::Text(TEXT("Next tip"), EType::Ui, Muted) ]
					], FMargin(22.f))
			]
		]
		+ SOverlay::Slot().VAlign(VAlign_Bottom).Padding(FMargin(SafeX, 0.f, SafeX, 40.f))
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().FillWidth(1.f)[ TextAttr(TAttribute<FText>::CreateLambda([this]() { FString S; Progress(S); return FText::FromString(S.ToUpper()); }), EType::Label, FSlateColor(Fg)) ]
				+ SHorizontalBox::Slot().AutoWidth()
				[
					SNew(SHorizontalBox).Visibility_Lambda([this]() { return IsReady() ? EVisibility::Visible : EVisibility::Collapsed; })
					+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 8.f, 0.f)[ KeyCap(TEXT("Enter"), TEXT("A")) ]
					+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)[ SailUI::Text(TEXT("Start sailing"), EType::Button, Accent) ]
				]
				+ SHorizontalBox::Slot().AutoWidth().Padding(16.f, 0.f, 0.f, 0.f)
					[ TextAttr(TAttribute<FText>::CreateLambda([this]() { FString S; return FText::FromString(FString::Printf(TEXT("%d%%"), FMath::RoundToInt(Progress(S) * 100.f))); }), EType::Label, FSlateColor(Muted)) ]
			]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 8.f, 0.f, 0.f)
			[
				SNew(SBox).HeightOverride(4.f)
				[
					SNew(SOverlay)
					+ SOverlay::Slot()[ SNew(SBorder).BorderImage(Rounded(Line, 2.f)) ]
					+ SOverlay::Slot().HAlign(HAlign_Left)
					[
						SNew(SBox).WidthOverride_Lambda([this]() { FString S; return FOptionalSize(Progress(S) * (GetCachedGeometry().GetLocalSize().X - 2.f * SafeX)); })
						[ SNew(SBorder).BorderImage(Rounded(Accent, 2.f)) ]
					]
				]
			]
		]
	];
}

float SSailLoading::Progress(FString& Stage) const
{
	UWorld* W = World.Get();
	if (!W) { Stage = TEXT("Loading"); return 0.f; }
	// World streaming (docs/world-streaming): the far coast's tiles within reach of the start are in (the near tiles were
	// read before the map started), and the physics' window has been marched (a streamed world re-marches it on the way).
	bool bFar = true;
	for (TActorIterator<ALakeTerrainActor> It(W); It; ++It) bFar = It->IsFarRingSettled();
	const ASailingGameMode* GM = W->GetAuthGameMode<ASailingGameMode>();
	const bool bSea = !GM || !GM->IsWindowMarching();
	// Stage 1: the shore around the start streamed in (the terrain's chunk queue empties).
	float Shore = 1.f;
	for (TActorIterator<ALakeTerrainActor> It(W); It; ++It)
	{
		const int32 P = It->GetPendingChunks();
		const_cast<SSailLoading*>(this)->InitialChunks = FMath::Max(InitialChunks, P);
		Shore = InitialChunks > 0 ? 1.f - float(P) / float(InitialChunks) : (P > 0 ? 0.f : 1.f);
	}
	bool bClouds = true;
	for (TActorIterator<ASailingEnvironment> It(W); It; ++It) bClouds = It->HasWeatherMap() && It->IsSkyReady();   // docs/cloud-popin/
	const ASailboatPawn* Pawn = W->GetFirstPlayerController() ? Cast<ASailboatPawn>(W->GetFirstPlayerController()->GetPawn()) : nullptr;
	const bool bBoat = Pawn != nullptr && FPlatformTime::Seconds() - ShownAt > 1.0;
	const bool bShaders = FShaderPipelineCache::NumPrecompilesRemaining() == 0;
	bool bTraffic = true;
	for (TActorIterator<ATrafficManager> It(W); It; ++It) bTraffic = It->IsPopulated();
	constexpr int32 N = 7;
	const bool Done[N] = { bFar, Shore >= 1.f, bSea, bClouds, bBoat, bShaders, bTraffic };
	static const TCHAR* Names[N] = { TEXT("Reading the far coast"), TEXT("Streaming shoreline and trees"), TEXT("Marching the sea"),
		TEXT("Baking cloud weather map"), TEXT("Rigging the boat and crew"), TEXT("Warming water and wake shaders"), TEXT("Placing traffic") };
	float Sum = 0.f;
	Stage = TEXT("Ready");
	for (int32 I = 0; I < N; ++I)
	{
		Sum += Done[I] ? 1.f : (I == 1 ? Shore : 0.f);
		if (!Done[I] && Stage == TEXT("Ready")) Stage = Names[I];
	}
	return Sum / float(N);
}

bool SSailLoading::IsReady() const
{
	FString S;
	return Progress(S) >= 0.999f;
}

FReply SSailLoading::OnKeyDown(const FGeometry&, const FKeyEvent& E)
{
	if (E.GetKey() == EKeys::I || E.GetKey() == EKeys::Gamepad_FaceButton_Left)
	{
		Tip = (Tip + 1) % int32(UE_ARRAY_COUNT(Tips));
		return FReply::Handled();
	}
	if (SailUI::IsConfirmKey(E.GetKey()) && IsReady())
	{
		OnStart.ExecuteIfBound();
		return FReply::Handled();
	}
	return FReply::Handled();
}

FReply SSailLoading::OnMouseButtonDown(const FGeometry&, const FPointerEvent&)
{
	if (IsReady()) OnStart.ExecuteIfBound();
	return FReply::Handled();
}
