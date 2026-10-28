#include "UI/SailPhotoPanel.h"
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

void SSailPhotoPanel::Construct(const FArguments& InArgs)
{
	using namespace SailUI;
	using namespace SailPhotoPanelImpl;
	Player = InArgs._Player;
	auto Shown = [this]()
	{
		const ASailboatPawn* P = Pawn();
		const ASailingHUD* Hud = Player.IsValid() ? Cast<ASailingHUD>(Player->GetHUD()) : nullptr;
		const bool bOn = P && P->IsPhotoMode() && P->GetFreeCamera() && !P->ArePhotoHintsHidden() && !(Hud && Hud->IsFrontEndOpen());
		return bOn ? EVisibility::HitTestInvisible : EVisibility::Collapsed;
	};
	auto Settings = [this]() { const ASailboatPawn* P = Pawn(); return P ? P->GetPhotoSettings() : FPhotoSettings(); };
	auto Page = [this]() { const ASailboatPawn* P = Pawn(); return P ? PhotoMath::PageOf(P->GetPhotoRow()) : 0; };

	// The tabs: the current page in the accent colour.
	TSharedRef<SHorizontalBox> Tabs = SNew(SHorizontalBox);
	for (int32 I = 0; I < PhotoMath::NumPages; ++I)
	{
		Tabs->AddSlot().AutoWidth().Padding(0.f, 0.f, 12.f, 0.f)
		[
			TextAttr(FText::FromString(PhotoMath::PageName(I)), EType::Eyebrow,
				TAttribute<FSlateColor>::CreateLambda([Page, I]() { return FSlateColor(Page() == I ? Accent : Dim); }))
		];
	}

	// Every row, shown on its own page: the row it is on is raised and shows its arrows; rows that do nothing just now
	// (manual distance outside manual focus, 2x below High) are dimmed.
	TSharedRef<SVerticalBox> Rows = SNew(SVerticalBox);
	for (int32 R = 0; R < int32(EPhotoRow::Count); ++R)
	{
		const EPhotoRow Row = EPhotoRow(R);
		auto Current = [this, Row]() { const ASailboatPawn* P = Pawn(); return P && P->GetPhotoRow() == Row; };
		auto Idle = [Settings, Row]() { return PhotoMath::RowIdle(Settings(), Row, ASailboatPawn::PhotoHighTier()); };
		Rows->AddSlot().AutoHeight().Padding(0.f, 2.f)
		[
			SNew(SBorder)
			.Visibility_Lambda([Page, Row]() { return Page() == PhotoMath::PageOf(Row) ? EVisibility::Visible : EVisibility::Collapsed; })
			.BorderImage_Lambda([Current]() { return Current() ? Rounded(Raise, RadiusButton) : Rounded(FLinearColor::Transparent, RadiusButton); })
			.Padding(FMargin(10.f, 6.f))
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().FillWidth(1.f).VAlign(VAlign_Center)
				[
					TextAttr(FText::FromString(PhotoMath::RowLabel(Row)), EType::Label,
						TAttribute<FSlateColor>::CreateLambda([Current, Idle]() { return FSlateColor(Idle() ? Dim : Current() ? Fg : Muted); }))
				]
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
				[
					TextAttr(TAttribute<FText>::CreateLambda([this, Row, Current]()
					{
						const ASailboatPawn* P = Pawn();
						const AFreeCamera* Cam = P ? P->GetFreeCamera() : nullptr;
						if (!Cam) return FText::GetEmpty();
						const FString V = PhotoMath::RowValue(P->GetPhotoSettings(), Row, Cam->GetCamera()->FieldOfView, Cam->GetRollDeg(), P->GetPhotoFocusM(), ASailboatPawn::PhotoHighTier());
						return FText::FromString(Current() ? FString::Printf(TEXT("←  %s  →"), *V) : V);
					}), EType::Ui, TAttribute<FSlateColor>::CreateLambda([Current, Idle]() { return FSlateColor(Idle() ? Dim : Current() ? Accent : Fg); }))
				]
			]
		];
	}

	auto Keys = []()
	{
		const bool bPad = UsingGamepad();
		auto L = [bPad](const TCHAR* A) { return SailingBindings::Label(A, false, bPad); };
		return FText::FromString(bPad
			? FString::Printf(TEXT("%s next row  ·  %s / %s change  ·  %s hide"), *L(TEXT("PhotoRowDown")), *L(TEXT("PhotoValueDown")), *L(TEXT("PhotoValueUp")), *L(TEXT("PhotoHideUI")))
			: FString::Printf(TEXT("%s / %s row  ·  %s / %s change  ·  %s / %s page  ·  %s hide"), *L(TEXT("PhotoRowUp")), *L(TEXT("PhotoRowDown")), *L(TEXT("PhotoValueDown")),
				*L(TEXT("PhotoValueUp")), *L(TEXT("PhotoPagePrev")), *L(TEXT("PhotoPageNext")), *L(TEXT("PhotoHideUI"))));
	};

	ChildSlot
	[
		SNew(SOverlay).Visibility_Lambda(Shown)
		+ SOverlay::Slot()
		[
			SNew(SPhotoGuides)
			.Crop_Lambda([Settings]() { return Settings().Crop; })
			.Grid_Lambda([Settings]() { return Settings().bGrid; })
		]
		+ SOverlay::Slot().HAlign(HAlign_Left).VAlign(VAlign_Top).Padding(HudMargin, SafeTop)
		[
			SNew(SBox).WidthOverride(330.f)
			[
				PanelBox(SNew(SVerticalBox)
					+ SVerticalBox::Slot().AutoHeight()[ Text(TEXT("Photo"), EType::CardTitleS) ]
					+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 8.f, 0.f, 8.f)[ Tabs ]
					+ SVerticalBox::Slot().AutoHeight()[ Rows ]
					+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 10.f, 0.f, 0.f)[ TextAttr(TAttribute<FText>::CreateLambda(Keys), EType::Small, FSlateColor(Muted), true) ],
					FMargin(14.f, 12.f))
			]
		]
	];
}
