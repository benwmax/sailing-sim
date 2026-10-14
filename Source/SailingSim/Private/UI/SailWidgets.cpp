#include "UI/SailWidgets.h"
#include "Framework/Application/SlateApplication.h"
#include "Rendering/DrawElements.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SSpacer.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/SLeafWidget.h"


namespace SailUI
{
	bool IsConfirmKey(const FKey& Key)
	{
		return Key == EKeys::Enter || Key == EKeys::SpaceBar || Key == EKeys::Gamepad_FaceButton_Bottom || Key == EKeys::Virtual_Accept;
	}
	bool IsBackKey(const FKey& Key)
	{
		return Key == EKeys::Escape || Key == EKeys::BackSpace || Key == EKeys::Gamepad_FaceButton_Right || Key == EKeys::Virtual_Back;
	}

	namespace
	{
		void Box(FSlateWindowElementList& Out, int32 Layer, const FGeometry& G, const FVector2D& Inset, const FSlateBrush* Brush, const FLinearColor& Tint = FLinearColor::White)
		{
			const FVector2D Size = G.GetLocalSize() - 2.0 * Inset;
			if (Size.X <= 0 || Size.Y <= 0) return;
			// MakeBox takes the colour from its tint, not the brush: carry the brush's colour in.
			FSlateDrawElement::MakeBox(Out, Layer, G.ToPaintGeometry(FVector2f(Size), FSlateLayoutTransform(FVector2f(Inset))), Brush, ESlateDrawEffect::None, Tint * Brush->TintColor.GetSpecifiedColor());
		}

		/** The draggable track with its yellow fill and knob. */
		class SSailTrack : public SLeafWidget
		{
		public:
			SLATE_BEGIN_ARGS(SSailTrack) {}
				SLATE_ATTRIBUTE(float, Fraction)
			SLATE_END_ARGS()
			void Construct(const FArguments& A) { Fraction = A._Fraction; }
			virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D(200.f, 22.f); }
			virtual int32 OnPaint(const FPaintArgs&, const FGeometry& G, const FSlateRect&, FSlateWindowElementList& Out, int32 Layer, const FWidgetStyle& Style, bool) const override
			{
				const FVector2D S = G.GetLocalSize();
				const float F = FMath::Clamp(Fraction.Get(0.f), 0.f, 1.f);
				const float Y = S.Y * 0.5f - 2.f;
				FSlateDrawElement::MakeBox(Out, Layer, G.ToPaintGeometry(FVector2f(S.X, 4.f), FSlateLayoutTransform(FVector2f(0.f, Y))), Rounded(Line, 2.f), ESlateDrawEffect::None, Style.GetColorAndOpacityTint() * Line);
				FSlateDrawElement::MakeBox(Out, Layer + 1, G.ToPaintGeometry(FVector2f(FMath::Max(S.X * F, 2.f), 4.f), FSlateLayoutTransform(FVector2f(0.f, Y))), Rounded(Accent, 2.f), ESlateDrawEffect::None, Style.GetColorAndOpacityTint() * Accent);
				const float K = 14.f;
				FSlateDrawElement::MakeBox(Out, Layer + 2, G.ToPaintGeometry(FVector2f(K, K), FSlateLayoutTransform(FVector2f(S.X * F - K * 0.5f, S.Y * 0.5f - K * 0.5f))), Rounded(Fg, K * 0.5f), ESlateDrawEffect::None, Style.GetColorAndOpacityTint() * Fg);
				return Layer + 2;
			}
		private:
			TAttribute<float> Fraction;
		};
	}

	TSharedRef<SWidget> Text(const FString& S, EType Type, const FLinearColor& Color, bool bWrap)
	{
		return SNew(STextBlock).Text(Txt(S, Type)).Font(Font(Type)).ColorAndOpacity(Color).AutoWrapText(bWrap)
			.LineHeightPercentage(Type == EType::Body || Type == EType::Small ? 1.3f : 1.f);
	}

	TSharedRef<SWidget> TextAttr(TAttribute<FText> S, EType Type, TAttribute<FSlateColor> Color, bool bWrap)
	{
		return SNew(STextBlock).Text(S).Font(Font(Type)).ColorAndOpacity(Color).AutoWrapText(bWrap)
			.LineHeightPercentage(Type == EType::Body || Type == EType::Small ? 1.3f : 1.f);
	}

	TSharedRef<SWidget> Pill(const FString& S, bool bAccent)
	{
		return SNew(SBorder).BorderImage(Rounded(bAccent ? Accent : Raise, 11.f, bAccent ? Accent : Line, 1.f)).Padding(FMargin(10.f, 3.f))
			[ Text(S, EType::Label, bAccent ? AccentInk : Fg) ];
	}

	TSharedRef<SWidget> PanelBox(TSharedRef<SWidget> Content, FMargin Padding, float Radius)
	{
		return SNew(SBorder).BorderImage(Rounded(IsLow() ? PanelSolid : Panel, Radius, Line, 1.f)).Padding(Padding)[ Content ];
	}

	TSharedRef<SWidget> KeyCap(const FString& Keyboard, const FString& Pad)
	{
		auto Label = [Keyboard, Pad]() { return FText::FromString(UsingGamepad() ? Pad : Keyboard); };
		auto Fill = [Pad]() -> const FSlateBrush*
		{
			if (!UsingGamepad()) return Rounded(Raise, 5.f, Line, 1.f);
			// Xbox face buttons in their colours (the mockup's glyphs).
			const FLinearColor C = Pad == TEXT("A") ? Hex(0x3BA55C) : Pad == TEXT("B") ? Hex(0xD9453C) : Pad == TEXT("X") ? Hex(0x2F7DD3)
				: Pad == TEXT("Y") ? Hex(0xE3B321) : Raise;
			return Rounded(C, 11.f, Line, 1.f);
		};
		return SNew(SBorder).BorderImage_Lambda(Fill).Padding(FMargin(8.f, 2.f)).VAlign(VAlign_Center)
			[ SNew(STextBlock).Text_Lambda(Label).Font(Font(EType::Label)).ColorAndOpacity(Fg) ];
	}

	TSharedRef<SWidget> PromptBar(TArray<TTuple<FString, FString, FString>> Prompts, const FString& Hint)
	{
		TSharedRef<SHorizontalBox> Row = SNew(SHorizontalBox);
		for (const TTuple<FString, FString, FString>& P : Prompts)
		{
			Row->AddSlot().AutoWidth().VAlign(VAlign_Center).Padding(0.f, 0.f, 8.f, 0.f)[ KeyCap(P.Get<0>(), P.Get<1>()) ];
			Row->AddSlot().AutoWidth().VAlign(VAlign_Center).Padding(0.f, 0.f, 24.f, 0.f)[ Text(P.Get<2>(), EType::Ui, Muted) ];
		}
		Row->AddSlot().FillWidth(1.f)[ SNew(SSpacer) ];
		Row->AddSlot().AutoWidth().VAlign(VAlign_Center)[ Text(Hint, EType::Small, Dim) ];
		return SNew(SBorder).BorderImage(Rounded(Ink.CopyWithNewOpacity(0.55f), 0.f)).Padding(FMargin(SafeX, 14.f))[ Row ];
	}

	TSharedRef<SWidget> Header(const FString& Eyebrow, const FString& Title, int32 Step)
	{
		TSharedRef<SHorizontalBox> Steps = SNew(SHorizontalBox);
		if (Step > 0)
		{
			static const TCHAR* Names[] = { TEXT("World"), TEXT("Start"), TEXT("Boat"), TEXT("Conditions"), TEXT("Mode") };
			for (int32 I = 0; I < 5; ++I)
			{
				const bool bDone = I + 1 < Step, bCur = I + 1 == Step;
				Steps->AddSlot().AutoWidth().Padding(4.f, 0.f)
				[
					SNew(SVerticalBox)
					+ SVerticalBox::Slot().AutoHeight()[ SNew(SBox).WidthOverride(110.f).HeightOverride(3.f)
						[ SNew(SBorder).BorderImage(Rounded(bCur ? Accent : (bDone ? Fg : Line), 1.f)) ] ]
					+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 6.f, 0.f, 0.f)
						[ Text(FString::Printf(TEXT("%d %s"), I + 1, Names[I]), EType::Label, bCur ? Accent : (bDone ? Fg : Dim)) ]
				];
			}
		}
		return SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().FillWidth(1.f).VAlign(VAlign_Bottom)
			[
				SNew(SVerticalBox)
				+ SVerticalBox::Slot().AutoHeight()[ Text(Eyebrow, EType::Eyebrow, Accent) ]
				+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 4.f, 0.f, 0.f)[ Text(Title, EType::ScreenTitle, Fg) ]
			]
			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Bottom).Padding(0.f, 0.f, 0.f, 14.f)[ Steps ];
	}

	TSharedRef<SSailButton> ActionButton(const FString& Label, FSimpleDelegate OnClicked, bool bPrimary)
	{
		return SNew(SSailButton).Look(bPrimary ? EButtonLook::Primary : EButtonLook::Secondary).OnClicked(OnClicked).Padding(FMargin(28.f, 14.f))
			[ SNew(SBox).HAlign(HAlign_Center)[ Text(Label, EType::Button, bPrimary ? AccentInk : Fg) ] ];
	}
}

// ---------------------------------------------------------------- SSailButton

void SSailButton::Construct(const FArguments& A)
{
	Look = A._Look;
	SelectedAttr = A._IsSelected;
	Enabled = A._IsEnabled;
	OnClicked = A._OnClicked;
	OnFocused = A._OnFocused;
	OnAdjust = A._OnAdjust;
	ChildSlot.Padding(A._Padding)[ A._Content.Widget ];
}

FReply SSailButton::OnKeyDown(const FGeometry& G, const FKeyEvent& E)
{
	if (SailUI::IsConfirmKey(E.GetKey()) && IsEnabledNow())
	{
		OnClicked.ExecuteIfBound();
		return FReply::Handled();
	}
	if (OnAdjust.IsBound() && (E.GetKey() == EKeys::Left || E.GetKey() == EKeys::Gamepad_DPad_Left || E.GetKey() == EKeys::Gamepad_LeftStick_Left))
	{
		OnAdjust.Execute(-1);
		return FReply::Handled();
	}
	if (OnAdjust.IsBound() && (E.GetKey() == EKeys::Right || E.GetKey() == EKeys::Gamepad_DPad_Right || E.GetKey() == EKeys::Gamepad_LeftStick_Right))
	{
		OnAdjust.Execute(+1);
		return FReply::Handled();
	}
	return FReply::Unhandled();
}

FReply SSailButton::OnMouseButtonDown(const FGeometry&, const FPointerEvent& E)
{
	if (E.GetEffectingButton() != EKeys::LeftMouseButton || !IsEnabledNow()) return FReply::Unhandled();
	bPressed = true;
	return FReply::Handled().SetUserFocus(SharedThis(this), EFocusCause::Mouse).CaptureMouse(SharedThis(this));
}

FReply SSailButton::OnMouseButtonUp(const FGeometry& G, const FPointerEvent& E)
{
	if (!bPressed) return FReply::Unhandled();
	bPressed = false;
	if (G.IsUnderLocation(E.GetScreenSpacePosition())) OnClicked.ExecuteIfBound();
	return FReply::Handled().ReleaseMouseCapture();
}

void SSailButton::OnMouseEnter(const FGeometry& G, const FPointerEvent& E)
{
	SCompoundWidget::OnMouseEnter(G, E);
	// The mouse moves focus, so there is only ever one highlighted item.
	if (IsEnabledNow() && !HasKeyboardFocus()) FSlateApplication::Get().SetUserFocus(0, SharedThis(this), EFocusCause::Mouse);
}

FReply SSailButton::OnFocusReceived(const FGeometry& G, const FFocusEvent& E)
{
	OnFocused.ExecuteIfBound();
	return SCompoundWidget::OnFocusReceived(G, E);
}

int32 SSailButton::OnPaint(const FPaintArgs& Args, const FGeometry& G, const FSlateRect& Culling, FSlateWindowElementList& Out, int32 Layer,
	const FWidgetStyle& Style, bool bParentEnabled) const
{
	const bool bFocus = HasKeyboardFocus(), bSel = SelectedAttr.Get(false), bOn = IsEnabledNow();
	FWidgetStyle S = Style;
	if (!bOn) S.BlendColorAndOpacityTint(FLinearColor(1, 1, 1, 0.45f));
	const FLinearColor T = S.GetColorAndOpacityTint();
	switch (Look)
	{
	case SailUI::EButtonLook::Card:
		SailUI::Box(Out, Layer, G, FVector2D::ZeroVector, SailUI::Rounded(SailUI::IsLow() ? SailUI::PanelSolid : SailUI::Panel, SailUI::RadiusCard, bSel ? SailUI::Selected : SailUI::Line, bSel ? 1.5f : 1.f), T);
		break;
	case SailUI::EButtonLook::Pin:
		SailUI::Box(Out, Layer, G, FVector2D::ZeroVector, SailUI::Rounded(bSel ? SailUI::Accent : SailUI::Chart, FMath::RoundToFloat(G.GetLocalSize().Y * 0.5f), SailUI::Fg, 2.f), T);
		break;
	case SailUI::EButtonLook::MenuItem:
		if (bFocus)
		{
			SailUI::Box(Out, Layer, G, FVector2D::ZeroVector, SailUI::Rounded(SailUI::Accent.CopyWithNewOpacity(0.16f), 3.f), T);
			FSlateDrawElement::MakeBox(Out, Layer + 1, G.ToPaintGeometry(FVector2f(4.f, G.GetLocalSize().Y), FSlateLayoutTransform()), SailUI::Rounded(SailUI::Accent, 1.f), ESlateDrawEffect::None, T * SailUI::Accent);
		}
		break;
	case SailUI::EButtonLook::Primary:
		SailUI::Box(Out, Layer, G, FVector2D::ZeroVector, SailUI::Rounded(SailUI::Accent, SailUI::RadiusButton), T);
		break;
	case SailUI::EButtonLook::Secondary:
		SailUI::Box(Out, Layer, G, FVector2D::ZeroVector, SailUI::Rounded(SailUI::Raise, SailUI::RadiusButton, SailUI::Line, 1.f), T);
		break;
	case SailUI::EButtonLook::Chip:
		SailUI::Box(Out, Layer, G, FVector2D::ZeroVector, SailUI::Rounded(bSel ? SailUI::Fg : SailUI::Raise, SailUI::RadiusButton, SailUI::Line, 1.f), T);
		break;
	}
	int32 Max = SCompoundWidget::OnPaint(Args, G, Culling, Out, Layer + 2, S, bParentEnabled);
	if (bSel && Look == SailUI::EButtonLook::Card)
	{
		// The tick in the top-right corner of a chosen card (drawn: the fonts have no check mark).
		const FVector2D Sz = G.GetLocalSize();
		const FVector2f O(Sz.X - 30.f, 14.f);
		FSlateDrawElement::MakeLines(Out, Max + 1, G.ToPaintGeometry(), { O + FVector2f(0.f, 7.f), O + FVector2f(5.f, 12.f), O + FVector2f(15.f, 0.f) },
			ESlateDrawEffect::None, SailUI::Accent * T, true, 3.f);
	}
	if (bFocus && Look != SailUI::EButtonLook::MenuItem)
	{
		// Focus: a 3 px yellow ring and a soft glow (white on the yellow button).
		const float R = Look == SailUI::EButtonLook::Pin ? FMath::RoundToFloat(G.GetLocalSize().Y * 0.5f) : (Look == SailUI::EButtonLook::Card ? SailUI::RadiusCard : SailUI::RadiusButton);
		const FLinearColor Ring = Look == SailUI::EButtonLook::Primary ? SailUI::Fg : SailUI::Accent;
		SailUI::Box(Out, Max + 2, G, FVector2D(-7.f), SailUI::Rounded(FLinearColor::Transparent, R + 7.f, Ring.CopyWithNewOpacity(0.22f), 6.f), T);
		SailUI::Box(Out, Max + 3, G, FVector2D(-2.f), SailUI::Rounded(FLinearColor::Transparent, R + 2.f, Ring, 3.f), T);
		Max += 3;
	}
	return Max + 1;
}

// ---------------------------------------------------------------- SSailSlider

void SSailSlider::Construct(const FArguments& A)
{
	Min = A._Min; Max = A._Max; Step = A._Step; Value = A._Value; Enabled = A._IsEnabled; OnChanged = A._OnChanged;
	TAttribute<FString> ValueText = A._ValueText;
	const TAttribute<float> V = Value;
	const float Lo = Min, Hi = Max;
	ChildSlot.Padding(FMargin(16.f, 12.f))
	[
		SNew(SHorizontalBox)
		+ SHorizontalBox::Slot().FillWidth(0.34f).VAlign(VAlign_Center)[ SailUI::Text(A._Label, SailUI::EType::Ui, SailUI::Fg) ]
		+ SHorizontalBox::Slot().FillWidth(0.46f).VAlign(VAlign_Center).Padding(8.f, 0.f)
		[
			SAssignNew(Track, SailUI::SSailTrack).Fraction_Lambda([V, Lo, Hi]() { return (V.Get(Lo) - Lo) / FMath::Max(Hi - Lo, 1e-3f); })
		]
		+ SHorizontalBox::Slot().FillWidth(0.2f).HAlign(HAlign_Right).VAlign(VAlign_Center)
			[ SNew(STextBlock).Text_Lambda([ValueText]() { return FText::FromString(ValueText.Get(FString())); }).Font(SailUI::Font(SailUI::EType::Value)).ColorAndOpacity(SailUI::Fg) ]
	];
}

void SSailSlider::Set(float V)
{
	V = FMath::Clamp(FMath::RoundToFloat((V - Min) / Step) * Step + Min, Min, Max);
	if (V != Value.Get(Min)) OnChanged.ExecuteIfBound(V);
}

FReply SSailSlider::OnKeyDown(const FGeometry& G, const FKeyEvent& E)
{
	const FKey K = E.GetKey();
	if (K == EKeys::Left || K == EKeys::Gamepad_DPad_Left || K == EKeys::Gamepad_LeftStick_Left) { Set(Value.Get(Min) - Step); return FReply::Handled(); }
	if (K == EKeys::Right || K == EKeys::Gamepad_DPad_Right || K == EKeys::Gamepad_LeftStick_Right) { Set(Value.Get(Min) + Step); return FReply::Handled(); }
	return FReply::Unhandled();
}

void SSailSlider::SetFromMouse(const FGeometry& G, const FPointerEvent& E)
{
	if (!Track.IsValid()) return;
	const FGeometry& TG = Track->GetTickSpaceGeometry();
	const float F = FMath::Clamp(float(TG.AbsoluteToLocal(E.GetScreenSpacePosition()).X / FMath::Max(TG.GetLocalSize().X, 1.0)), 0.f, 1.f);
	Set(Min + F * (Max - Min));
}

FReply SSailSlider::OnMouseButtonDown(const FGeometry& G, const FPointerEvent& E)
{
	if (E.GetEffectingButton() != EKeys::LeftMouseButton || !Enabled.Get(true)) return FReply::Unhandled();
	bDragging = true;
	SetFromMouse(G, E);
	return FReply::Handled().CaptureMouse(SharedThis(this)).SetUserFocus(SharedThis(this), EFocusCause::Mouse);
}

FReply SSailSlider::OnMouseMove(const FGeometry& G, const FPointerEvent& E)
{
	if (bDragging) { SetFromMouse(G, E); return FReply::Handled(); }
	return FReply::Unhandled();
}

FReply SSailSlider::OnMouseButtonUp(const FGeometry&, const FPointerEvent&)
{
	if (!bDragging) return FReply::Unhandled();
	bDragging = false;
	return FReply::Handled().ReleaseMouseCapture();
}

void SSailSlider::OnMouseEnter(const FGeometry& G, const FPointerEvent& E)
{
	SCompoundWidget::OnMouseEnter(G, E);
	if (Enabled.Get(true) && !HasKeyboardFocus()) FSlateApplication::Get().SetUserFocus(0, SharedThis(this), EFocusCause::Mouse);
}

int32 SSailSlider::OnPaint(const FPaintArgs& Args, const FGeometry& G, const FSlateRect& Culling, FSlateWindowElementList& Out, int32 Layer,
	const FWidgetStyle& Style, bool bParentEnabled) const
{
	FWidgetStyle S = Style;
	if (!Enabled.Get(true)) S.BlendColorAndOpacityTint(FLinearColor(1, 1, 1, 0.4f));
	SailUI::Box(Out, Layer, G, FVector2D::ZeroVector, SailUI::Rounded(SailUI::IsLow() ? SailUI::PanelSolid : SailUI::Panel, SailUI::RadiusButton, SailUI::Line, 1.f), S.GetColorAndOpacityTint());
	int32 Top = SCompoundWidget::OnPaint(Args, G, Culling, Out, Layer + 1, S, bParentEnabled);
	if (HasKeyboardFocus())
	{
		SailUI::Box(Out, Top + 1, G, FVector2D(-2.f), SailUI::Rounded(FLinearColor::Transparent, SailUI::RadiusButton + 2.f, SailUI::Accent, 3.f));
		++Top;
	}
	return Top + 1;
}

// ---------------------------------------------------------------- SSailChoice

void SSailChoice::Construct(const FArguments& A)
{
	Options = A._Options; Index = A._Index; Enabled = A._IsEnabled; OnChanged = A._OnChanged;
	TSharedRef<SHorizontalBox> Chips = SNew(SHorizontalBox);
	for (int32 I = 0; I < Options.Num(); ++I)
	{
		const TAttribute<int32> Idx = Index;
		Chips->AddSlot().AutoWidth().Padding(4.f, 0.f)
		[
			SNew(SBorder).Padding(FMargin(10.f, 4.f))
			.BorderImage_Lambda([Idx, I]() { return SailUI::Rounded(Idx.Get(0) == I ? SailUI::Fg : SailUI::Raise, SailUI::RadiusButton, SailUI::Line, 1.f); })
			.OnMouseButtonDown_Lambda([this, I](const FGeometry&, const FPointerEvent&) { if (Enabled.Get(true)) OnChanged.ExecuteIfBound(I); return FReply::Handled(); })
			[
				SNew(STextBlock).Text(FText::FromString(Options[I])).Font(SailUI::Font(SailUI::EType::Ui))
				.ColorAndOpacity_Lambda([Idx, I]() { return FSlateColor(Idx.Get(0) == I ? SailUI::Ink : SailUI::Fg); })
			]
		];
	}
	TSharedRef<SVerticalBox> Col = SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight()
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().FillWidth(0.3f).VAlign(VAlign_Center)[ SailUI::Text(A._Label, SailUI::EType::Ui, SailUI::Fg) ]
			+ SHorizontalBox::Slot().FillWidth(0.7f).HAlign(HAlign_Right).VAlign(VAlign_Center)[ Chips ]
		];
	if (!A._Note.IsEmpty()) Col->AddSlot().AutoHeight().Padding(0.f, 6.f, 0.f, 0.f)[ SailUI::Text(A._Note, SailUI::EType::Small, SailUI::Muted, true) ];
	ChildSlot.Padding(FMargin(16.f, 12.f))[ Col ];
}

FReply SSailChoice::OnKeyDown(const FGeometry&, const FKeyEvent& E)
{
	const FKey K = E.GetKey();
	const int32 N = Options.Num();
	if (N == 0) return FReply::Unhandled();
	if (K == EKeys::Left || K == EKeys::Gamepad_DPad_Left || K == EKeys::Gamepad_LeftStick_Left) { OnChanged.ExecuteIfBound((Index.Get(0) + N - 1) % N); return FReply::Handled(); }
	if (K == EKeys::Right || K == EKeys::Gamepad_DPad_Right || K == EKeys::Gamepad_LeftStick_Right) { OnChanged.ExecuteIfBound((Index.Get(0) + 1) % N); return FReply::Handled(); }
	return FReply::Unhandled();
}

void SSailChoice::OnMouseEnter(const FGeometry& G, const FPointerEvent& E)
{
	SCompoundWidget::OnMouseEnter(G, E);
	if (Enabled.Get(true) && !HasKeyboardFocus()) FSlateApplication::Get().SetUserFocus(0, SharedThis(this), EFocusCause::Mouse);
}

int32 SSailChoice::OnPaint(const FPaintArgs& Args, const FGeometry& G, const FSlateRect& Culling, FSlateWindowElementList& Out, int32 Layer,
	const FWidgetStyle& Style, bool bParentEnabled) const
{
	FWidgetStyle S = Style;
	if (!Enabled.Get(true)) S.BlendColorAndOpacityTint(FLinearColor(1, 1, 1, 0.4f));
	SailUI::Box(Out, Layer, G, FVector2D::ZeroVector, SailUI::Rounded(SailUI::IsLow() ? SailUI::PanelSolid : SailUI::Panel, SailUI::RadiusButton, SailUI::Line, 1.f), S.GetColorAndOpacityTint());
	int32 Top = SCompoundWidget::OnPaint(Args, G, Culling, Out, Layer + 1, S, bParentEnabled);
	if (HasKeyboardFocus())
	{
		SailUI::Box(Out, Top + 1, G, FVector2D(-2.f), SailUI::Rounded(FLinearColor::Transparent, SailUI::RadiusButton + 2.f, SailUI::Accent, 3.f));
		++Top;
	}
	return Top + 1;
}
