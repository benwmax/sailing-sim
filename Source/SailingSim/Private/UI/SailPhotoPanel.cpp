#include "UI/SailPhotoPanel.h"
#include "BenchRunner.h"
#include "UI/SailWidgets.h"
#include "UI/SailUIStyle.h"
#include "SailboatPawn.h"
#include "SailingHUD.h"
#include "SailingBindings.h"
#include "FreeCamera.h"
#include "PhotoSettings.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/PlayerController.h"
#include "Rendering/DrawElements.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SWrapBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SLeafWidget.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"

namespace SailPhotoPanelImpl
{
	using namespace SailUI;

	/** The frame guides: the crop guide's frame (the frame outside it dimmed) and the thirds grid inside it. */
	class SPhotoGuides : public SLeafWidget
	{
	public:
		SLATE_BEGIN_ARGS(SPhotoGuides) {}
			SLATE_ATTRIBUTE(EPhotoCrop, Crop)
			SLATE_ATTRIBUTE(bool, Grid)
		SLATE_END_ARGS()

		void Construct(const FArguments& InArgs) { Crop = InArgs._Crop; Grid = InArgs._Grid; }
		virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D(16.0, 16.0); }

		virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& G, const FSlateRect& Culling, FSlateWindowElementList& Out,
			int32 Layer, const FWidgetStyle& Style, bool bParentEnabled) const override
		{
			const FVector2f S = FVector2f(G.GetLocalSize());
			const EPhotoCrop C = Crop.Get(EPhotoCrop::None);
			const FVector4f R = PhotoMath::CropRect(C, S.X, S.Y);
			const FLinearColor Shade(0.f, 0.f, 0.f, 0.45f), Lines(1.f, 1.f, 1.f, 0.55f);
			if (C != EPhotoCrop::None)
			{
				auto Box = [&](float X, float Y, float W, float H)
				{
					if (W > 0.5f && H > 0.5f) FSlateDrawElement::MakeBox(Out, Layer, G.ToPaintGeometry(FVector2f(W, H), FSlateLayoutTransform(FVector2f(X, Y))), White(), ESlateDrawEffect::None, Shade);
				};
				Box(0.f, 0.f, S.X, R.Y);
				Box(0.f, R.Y + R.W, S.X, S.Y - R.Y - R.W);
				Box(0.f, R.Y, R.X, R.W);
				Box(R.X + R.Z, R.Y, S.X - R.X - R.Z, R.W);
				FSlateDrawElement::MakeLines(Out, Layer + 1, G.ToPaintGeometry(), { FVector2f(R.X, R.Y), FVector2f(R.X + R.Z, R.Y), FVector2f(R.X + R.Z, R.Y + R.W),
					FVector2f(R.X, R.Y + R.W), FVector2f(R.X, R.Y) }, ESlateDrawEffect::None, Lines, true, 1.5f);
			}
			if (Grid.Get(false))
			{
				for (int32 I = 1; I <= 2; ++I)
				{
					const float X = R.X + R.Z * I / 3.f, Y = R.Y + R.W * I / 3.f;
					FSlateDrawElement::MakeLines(Out, Layer + 1, G.ToPaintGeometry(), { FVector2f(X, R.Y), FVector2f(X, R.Y + R.W) }, ESlateDrawEffect::None, Lines, true, 1.f);
					FSlateDrawElement::MakeLines(Out, Layer + 1, G.ToPaintGeometry(), { FVector2f(R.X, Y), FVector2f(R.X + R.Z, Y) }, ESlateDrawEffect::None, Lines, true, 1.f);
				}
			}
			return Layer + 1;
		}

	private:
		TAttribute<EPhotoCrop> Crop;
		TAttribute<bool> Grid;
	};
}

ASailboatPawn* SSailPhotoPanel::Pawn() const
{
	return Player.IsValid() ? Cast<ASailboatPawn>(Player->GetPawn()) : nullptr;
}

FString SSailPhotoPanel::GlyphText(const FString& PadLabel)
{
	if (PadLabel == TEXT("D-pad up")) return TEXT("\u2191");
	if (PadLabel == TEXT("D-pad down")) return TEXT("\u2193");
	if (PadLabel == TEXT("D-pad left")) return TEXT("\u2190");
	if (PadLabel == TEXT("D-pad right")) return TEXT("\u2192");
	if (PadLabel == TEXT("Left stick press")) return TEXT("L3");
	if (PadLabel == TEXT("Right stick press")) return TEXT("R3");
	if (PadLabel == TEXT("Left stick")) return TEXT("L");
	if (PadLabel == TEXT("Right stick")) return TEXT("R");
	return PadLabel;
}

namespace SailPhotoPanelImpl
{
	/** A command's keyboard key and controller glyph text, as KeyCap draws them (arrows for the arrow keys). */
	FString KeyText(const TCHAR* Action)
	{
		const FString K = SailingBindings::Label(Action, false, false);
		if (K == TEXT("Up")) return TEXT("\u2191");
		if (K == TEXT("Down")) return TEXT("\u2193");
		if (K == TEXT("Left")) return TEXT("\u2190");
		if (K == TEXT("Right")) return TEXT("\u2192");
		return K;
	}
	FString PadText(const TCHAR* Action) { return SSailPhotoPanel::GlyphText(SailingBindings::Label(Action, false, true)); }
	/** Two commands on one cap: two arrows make one D-pad (or one pair of arrow keys); anything else "A / B". */
	FString Join(const FString& A, const FString& B)
	{
		auto Arrow = [](const FString& S) { return S.Len() == 1 && S[0] >= TCHAR(0x2190) && S[0] <= TCHAR(0x2195); };
		return Arrow(A) && Arrow(B) ? A + B : A + TEXT(" / ") + B;
	}
}

FString SSailPhotoPanel::Signature() const
{
	// The card is rebuilt when what it shows by construction changes: the UI mode, the device, a rebound key.
	using namespace SailPhotoPanelImpl;
	FString S = FString::Printf(TEXT("%d|%d"), int32(SailUI::UiMode()), SailUI::UsingGamepad() ? 1 : 0);
	for (const TCHAR* A : { TEXT("PhotoShot"), TEXT("PhotoBack"), TEXT("PhotoOrbit"), TEXT("PhotoHideUI"), TEXT("PhotoPagePrev"), TEXT("PhotoPageNext"),
		TEXT("PhotoRowUp"), TEXT("PhotoRowDown"), TEXT("PhotoValueDown"), TEXT("PhotoValueUp"), TEXT("PhotoAlt"), TEXT("PhotoResetTab") })
	{
		S += TEXT("|") + KeyText(A) + TEXT(",") + PadText(A);
	}
	return S;
}

void SSailPhotoPanel::Construct(const FArguments& InArgs)
{
	using namespace SailUI;
	using namespace SailPhotoPanelImpl;
	Player = InArgs._Player;
	auto Shown = [this]()
	{
		const ASailboatPawn* P = Pawn();
		const ASailingHUD* Hud = Player.IsValid() ? Cast<ASailingHUD>(Player->GetHUD()) : nullptr;
		static SailingArgs::FCachedFlag NoHudArg(TEXT("SailingNoHud"));
		const bool bOn = P && ShouldShow(P->IsPhotoMode(), P->GetFreeCamera() != nullptr, P->ArePhotoHintsHidden(), Hud && Hud->IsFrontEndOpen(), NoHudArg.Get());
		return bOn ? EVisibility::SelfHitTestInvisible : EVisibility::Collapsed;
	};
	auto Settings = [this]() { const ASailboatPawn* P = Pawn(); return P ? P->GetPhotoSettings() : FPhotoSettings(); };
	auto CardVisible = [this]()
	{
		const ASailboatPawn* P = Pawn();
		if (!P || !P->IsPhotoPanelOpen()) return EVisibility::Collapsed;
		return P->IsPhotoPointerShown() ? EVisibility::Visible : EVisibility::HitTestInvisible;   // clicks only with the pointer out
	};

	ChildSlot
	[
		SNew(SOverlay).Visibility_Lambda(Shown)
		+ SOverlay::Slot()
		[
			SNew(SPhotoGuides).Visibility(EVisibility::HitTestInvisible)
			.Crop_Lambda([Settings]() { return Settings().Crop; })
			.Grid_Lambda([Settings]() { return Settings().bGrid; })
		]
		+ SOverlay::Slot().HAlign(HAlign_Left).VAlign(VAlign_Top).Padding(HudMargin, SafeTop, HudMargin, 0.f)
		[
			// On the left; Tick slides it across (a render transform, which hit testing follows) when the boat is behind it.
			SAssignNew(CardHolder, SBox).WidthOverride(400.f).Visibility_Lambda(CardVisible)
		]
	];
	BuiltFor = Signature();
	CardHolder->SetContent(BuildCard());
}

void SSailPhotoPanel::Tick(const FGeometry& AllottedGeometry, const double InCurrentTime, const float InDeltaTime)
{
	SCompoundWidget::Tick(AllottedGeometry, InCurrentTime, InDeltaTime);
	const ASailboatPawn* P = Pawn();
	if (!P || !P->IsPhotoMode() || !CardHolder.IsValid()) return;
	const FString Now = Signature();
	if (Now != BuiltFor)
	{
		BuiltFor = Now;
		CardHolder->SetContent(BuildCard());
	}
	// Out of the way (Bean's pick): the boat's middle, a few metres up her mast, against the screen's thirds.
	FVector2D Screen;
	int32 W = 0, H = 0;
	Player->GetViewportSize(W, H);
	if (W > 0 && Player->ProjectWorldLocationToScreen(P->GetActorLocation() + FVector(0.0, 0.0, 300.0), Screen, true))
	{
		bOnRight = PhotoMath::PanelOnRight(bOnRight, float(Screen.X / W));
	}
	const float Target = bOnRight ? 1.f : 0.f;
	SideT = FMath::Abs(Target - SideT) < 0.002f ? Target : FMath::Lerp(SideT, Target, 1.f - FMath::Exp(-InDeltaTime / 0.08f));
	const float Travel = FMath::Max(0.f, float(AllottedGeometry.GetLocalSize().X) - 2.f * SailUI::HudMargin - float(CardHolder->GetDesiredSize().X));
	CardHolder->SetRenderTransform(TOptional<FSlateRenderTransform>(FSlateRenderTransform(FVector2f(SideT * Travel, 0.f))));
}

TSharedRef<SWidget> SSailPhotoPanel::BuildCard()
{
	using namespace SailUI;
	using namespace SailPhotoPanelImpl;
	const EUiMode Mode = UiMode();
	const bool bHelpful = Mode == EUiMode::Helpful;
	TWeakPtr<SSailPhotoPanel> WeakSelf = StaticCastSharedRef<SSailPhotoPanel>(AsShared());
	auto PawnOf = [WeakSelf]() -> ASailboatPawn* { TSharedPtr<SSailPhotoPanel> S = WeakSelf.Pin(); return S.IsValid() ? S->Pawn() : nullptr; };
	auto Page = [PawnOf]() { const ASailboatPawn* P = PawnOf(); return P ? PhotoMath::PageOf(P->GetPhotoRow()) : 0; };
	auto Settings = [PawnOf]() { const ASailboatPawn* P = PawnOf(); return P ? P->GetPhotoSettings() : FPhotoSettings(); };
	auto Click = [](TFunction<void()> Do)
	{
		return [Do](const FGeometry&, const FPointerEvent& E)
		{
			if (E.GetEffectingButton() != EKeys::LeftMouseButton) return FReply::Unhandled();
			Do();
			return FReply::Handled();
		};
	};

	// The tabs, between the bumpers' glyphs (Page Up and Page Down on a keyboard); the current one in the accent colour
	// on a raised label, each clickable.
	TSharedRef<SHorizontalBox> Tabs = SNew(SHorizontalBox);
	Tabs->AddSlot().AutoWidth().VAlign(VAlign_Center).Padding(0.f, 0.f, 6.f, 0.f)[ KeyCap(KeyText(TEXT("PhotoPagePrev")), PadText(TEXT("PhotoPagePrev"))) ];
	for (int32 I = 0; I < PhotoMath::NumPages; ++I)
	{
		// (sentence case at the Ui size: the tracked upper-case eyebrow cut the names short in 360 px, "Len Foc Ligi")
		Tabs->AddSlot().AutoWidth().VAlign(VAlign_Center).Padding(1.f, 0.f)
		[
			SNew(SBorder)
			.BorderImage_Lambda([Page, I]() { return Page() == I ? Rounded(Raise, RadiusButton) : Rounded(FLinearColor::Transparent, RadiusButton); })
			.Padding(FMargin(6.f, 4.f)).HAlign(HAlign_Center)
			.OnMouseButtonDown_Lambda(Click([PawnOf, I]() { if (ASailboatPawn* P = PawnOf()) P->SelectPhotoPage(I); }))
			[
				TextAttr(FText::FromString(PhotoMath::PageName(I)), EType::Small,
					TAttribute<FSlateColor>::CreateLambda([Page, I]() { return FSlateColor(Page() == I ? Accent : Muted); }))
			]
		];
	}
	Tabs->AddSlot().FillWidth(1.f)[ SNew(SBox) ];
	Tabs->AddSlot().AutoWidth().VAlign(VAlign_Center).Padding(6.f, 0.f, 0.f, 0.f)[ KeyCap(KeyText(TEXT("PhotoPageNext")), PadText(TEXT("PhotoPageNext"))) ];

	// The rows on the tab: Helpful shows them all with a line on the current one; Natural only the current one. A row is
	// raised when it is the current one and shows its arrows; rows that do nothing just now are dimmed.
	TSharedRef<SVerticalBox> Rows = SNew(SVerticalBox);
	for (int32 R = 0; R < int32(EPhotoRow::Count); ++R)
	{
		const EPhotoRow Row = EPhotoRow(R);
		auto Current = [PawnOf, Row]() { const ASailboatPawn* P = PawnOf(); return P && P->GetPhotoRow() == Row; };
		auto Idle = [Settings, Row]() { return PhotoMath::RowIdle(Settings(), Row, ASailboatPawn::PhotoHighTier()); };
		auto Arrow = [Current, Click, PawnOf](const TCHAR* Glyph, int32 Dir)
		{
			return SNew(SBorder).BorderImage(Rounded(FLinearColor::Transparent, RadiusButton)).Padding(FMargin(6.f, 0.f))
				.Visibility_Lambda([Current]() { return Current() ? EVisibility::Visible : EVisibility::Hidden; })
				.OnMouseButtonDown_Lambda(Click([PawnOf, Dir]() { if (ASailboatPawn* P = PawnOf()) P->StepPhotoValue(Dir); }))
				[ Text(Glyph, EType::Ui, Accent) ];
		};
		Rows->AddSlot().AutoHeight().Padding(0.f, 1.f)
		[
			SNew(SBorder)
			.Visibility_Lambda([Page, Row, Current, bHelpful]() { return Page() == PhotoMath::PageOf(Row) && (bHelpful || Current()) ? EVisibility::Visible : EVisibility::Collapsed; })
			.BorderImage_Lambda([Current]() { return Current() ? Rounded(Raise, RadiusButton) : Rounded(FLinearColor::Transparent, RadiusButton); })
			.Padding(FMargin(10.f, 6.f))
			.OnMouseButtonDown_Lambda(Click([PawnOf, Row]() { if (ASailboatPawn* P = PawnOf()) P->SelectPhotoRow(Row); }))
			[
				SNew(SVerticalBox)
				+ SVerticalBox::Slot().AutoHeight()
				[
					SNew(SHorizontalBox)
					+ SHorizontalBox::Slot().FillWidth(1.f).VAlign(VAlign_Center)
					[
						TextAttr(FText::FromString(PhotoMath::RowLabel(Row)), EType::Label,
							TAttribute<FSlateColor>::CreateLambda([Current, Idle]() { return FSlateColor(Idle() ? Dim : Current() ? Fg : Muted); }))
					]
					+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)[ Arrow(TEXT("\u25C2"), -1) ]
					+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
					[
						TextAttr(TAttribute<FText>::CreateLambda([PawnOf, Row]()
						{
							const ASailboatPawn* P = PawnOf();
							const AFreeCamera* Cam = P ? P->GetFreeCamera() : nullptr;
							if (!Cam) return FText::GetEmpty();
							return FText::FromString(PhotoMath::RowValue(P->GetPhotoSettings(), Row, Cam->GetCamera()->FieldOfView, Cam->GetRollDeg(), P->GetPhotoFocusM(), ASailboatPawn::PhotoHighTier()));
						}), EType::Ui, TAttribute<FSlateColor>::CreateLambda([Current, Idle]() { return FSlateColor(Idle() ? Dim : Current() ? Accent : Fg); }))
					]
					+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)[ Arrow(TEXT("\u25B8"), 1) ]
				]
				+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 4.f, 0.f, 0.f)
				[
					SNew(SBox).Visibility_Lambda([Current, bHelpful]() { return bHelpful && Current() ? EVisibility::Visible : EVisibility::Collapsed; })
					[ Text(PhotoMath::RowHelp(Row), EType::Small, Muted, true) ]
				]
			]
		];
	}

	// The prompts, as glyphs (#732's): Helpful names every control; Natural only the shutter and back.
	TSharedRef<SWrapBox> Prompts = SNew(SWrapBox).UseAllottedSize(true).InnerSlotPadding(FVector2D(14.0, 6.0));
	auto Prompt = [&Prompts](const FString& Kb, const FString& Pad, const TCHAR* Label)
	{
		Prompts->AddSlot()
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0.f, 0.f, 6.f, 0.f)[ KeyCap(Kb, Pad) ]
			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)[ Text(Label, EType::Small, Muted) ]
		];
	};
	const bool bPad = UsingGamepad();
	Prompt(KeyText(TEXT("PhotoShot")), PadText(TEXT("PhotoShot")), TEXT("Photo"));
	if (bHelpful)
	{
		Prompt(Join(KeyText(TEXT("PhotoRowUp")), KeyText(TEXT("PhotoRowDown"))), Join(PadText(TEXT("PhotoRowUp")), PadText(TEXT("PhotoRowDown"))), TEXT("Row"));
		Prompt(Join(KeyText(TEXT("PhotoValueDown")), KeyText(TEXT("PhotoValueUp"))), Join(PadText(TEXT("PhotoValueDown")), PadText(TEXT("PhotoValueUp"))), TEXT("Change"));
		Prompt(KeyText(TEXT("PhotoAlt")), PadText(TEXT("PhotoAlt")), bPad ? TEXT("Hold: zoom, tilt, speed") : TEXT("Hold: pointer"));
		Prompt(KeyText(TEXT("PhotoResetTab")), PadText(TEXT("PhotoResetTab")), bPad ? TEXT("Hold: reset tab") : TEXT("Reset tab"));
		Prompt(KeyText(TEXT("PhotoOrbit")), PadText(TEXT("PhotoOrbit")), TEXT("Orbit / fly"));
		Prompt(KeyText(TEXT("PhotoHideUI")), PadText(TEXT("PhotoHideUI")), TEXT("Hide"));
	}
	Prompt(KeyText(TEXT("PhotoBack")), PadText(TEXT("PhotoBack")), TEXT("Back"));

	return PanelBox(SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight()[ Tabs ]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 10.f, 0.f, 0.f)[ Rows ]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 12.f, 0.f, 0.f)[ Prompts ],
		FMargin(14.f, 12.f));
}
