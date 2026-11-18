#include "UI/SailWidgets.h"
#include "Framework/Application/SlateApplication.h"
#include "Rendering/DrawElements.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Fonts/FontMeasure.h"
#include "Internationalization/BreakIterator.h"
#include "Internationalization/IBreakIterator.h"
#include "Rendering/SlateRenderer.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SSpacer.h"
#include "Widgets/Layout/SWrapBox.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/SLeafWidget.h"


namespace SailUI
{
	bool IsConfirmKey(const FKey& Key)
	{
		return Key == EKeys::Enter || Key == EKeys::SpaceBar || Key == EKeys::Gamepad_FaceButton_Bottom || Key == EKeys::Virtual_Gamepad_Accept.GetVirtualKey();
	}
	bool IsBackKey(const FKey& Key)
	{
		return Key == EKeys::Escape || Key == EKeys::BackSpace || Key == EKeys::Gamepad_FaceButton_Right || Key == EKeys::Virtual_Gamepad_Back.GetVirtualKey();
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

		/** The draggable track with its accent fill and knob. */
		class SSailTrack : public SLeafWidget
		{
		public:
			SLATE_BEGIN_ARGS(SSailTrack) {}
				SLATE_ATTRIBUTE(float, Fraction)
			SLATE_END_ARGS()
			void Construct(const FArguments& A) { Fraction = A._Fraction; bPaper = OnPaper(); }
			virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D(200.f, 22.f); }
			virtual int32 OnPaint(const FPaintArgs&, const FGeometry& G, const FSlateRect&, FSlateWindowElementList& Out, int32 Layer, const FWidgetStyle& Style, bool) const override
			{
				const FVector2D S = G.GetLocalSize();
				const float F = FMath::Clamp(Fraction.Get(0.f), 0.f, 1.f);
				const float Y = S.Y * 0.5f - 2.f;
				FSlateDrawElement::MakeBox(Out, Layer, G.ToPaintGeometry(FVector2f(S.X, 4.f), FSlateLayoutTransform(FVector2f(0.f, Y))), Rounded(Surface(bPaper, Line), 2.f), ESlateDrawEffect::None, Style.GetColorAndOpacityTint() * Surface(bPaper, Line));
				FSlateDrawElement::MakeBox(Out, Layer + 1, G.ToPaintGeometry(FVector2f(FMath::Max(S.X * F, 2.f), 4.f), FSlateLayoutTransform(FVector2f(0.f, Y))), Rounded(Surface(bPaper, Accent), 2.f), ESlateDrawEffect::None, Style.GetColorAndOpacityTint() * Surface(bPaper, Accent));
				const float K = 14.f;
				FSlateDrawElement::MakeBox(Out, Layer + 2, G.ToPaintGeometry(FVector2f(K, K), FSlateLayoutTransform(FVector2f(S.X * F - K * 0.5f, S.Y * 0.5f - K * 0.5f))), Rounded(Surface(bPaper, Fg), K * 0.5f), ESlateDrawEffect::None, Style.GetColorAndOpacityTint() * Surface(bPaper, Fg));
				return Layer + 2;
			}
		private:
			TAttribute<float> Fraction;
			bool bPaper = false;
		};
	}

	namespace
	{
		/** The usual line breaks, less the one after a slash inside a word: "J/22" wrapped as "J/" and "22". (No face here
		 *  has a no-break glyph to put in the text instead.) Each text block gets its own: an iterator holds its place. */
		class FSlashKeptLineBreaks final : public IBreakIterator
		{
		public:
			FSlashKeptLineBreaks() : Inner(FBreakIterator::CreateLineBreakIterator()) {}
			virtual void SetString(FString&& InString) override { Kept = MoveTemp(InString); Inner->SetStringRef(FStringView(Kept)); }
			virtual void SetStringRef(FStringView InString) override { Kept = FString(InString); Inner->SetStringRef(FStringView(Kept)); }
			virtual int32 GetCurrentPosition() const override { return Inner->GetCurrentPosition(); }
			virtual int32 ResetToBeginning() override { return Inner->ResetToBeginning(); }
			virtual int32 ResetToEnd() override { return Inner->ResetToEnd(); }
			virtual int32 MoveToPrevious() override { return Back(Inner->MoveToPrevious()); }
			virtual int32 MoveToNext() override { return On(Inner->MoveToNext()); }
			virtual int32 MoveToCandidateBefore(const int32 InIndex) override { return Back(Inner->MoveToCandidateBefore(InIndex)); }
			virtual int32 MoveToCandidateAfter(const int32 InIndex) override { return On(Inner->MoveToCandidateAfter(InIndex)); }
		private:
			bool Glued(int32 At) const { return At > 0 && At < Kept.Len() && Kept[At - 1] == TCHAR('/') && !FChar::IsWhitespace(Kept[At]); }
			int32 On(int32 At) { while (At != INDEX_NONE && Glued(At)) At = Inner->MoveToNext(); return At; }
			int32 Back(int32 At) { while (At != INDEX_NONE && Glued(At)) At = Inner->MoveToPrevious(); return At; }
			TSharedRef<IBreakIterator> Inner;
			FString Kept;
		};
		TSharedPtr<IBreakIterator> LineBreaksFor(bool bWrap) { return bWrap ? TSharedPtr<IBreakIterator>(MakeShared<FSlashKeptLineBreaks>()) : TSharedPtr<IBreakIterator>(); }
	}

	TSharedRef<SWidget> Text(const FString& S, EType Type, const FLinearColor& Color, bool bWrap)
	{
		// (On a paper sheet the glass token becomes its paper twin: SailUI::Surface.)
		return SNew(STextBlock).Text(Txt(S, Type)).Font(Font(Type)).ColorAndOpacity(OnSurface(Color)).AutoWrapText(bWrap).LineBreakPolicy(LineBreaksFor(bWrap))
			.LineHeightPercentage(Type == EType::Body || Type == EType::Small ? 1.3f : 1.f);
	}

	TSharedRef<SWidget> TextOverScene(const FString& S, EType Type, const FLinearColor& Color, bool bWrap)
	{
		// Text with no panel under it lies on whatever the world shows (a bright sky as often as dark water): an ink shadow
		// keeps its edge.
		return SNew(STextBlock).Text(Txt(S, Type)).Font(Font(Type)).ColorAndOpacity(Color).AutoWrapText(bWrap).LineBreakPolicy(LineBreaksFor(bWrap))
			.ShadowOffset(FVector2D(1.f, 1.5f)).ShadowColorAndOpacity(Ink.CopyWithNewOpacity(0.7f))
			.LineHeightPercentage(Type == EType::Body || Type == EType::Small ? 1.3f : 1.f);
	}

	TSharedRef<SWidget> TextAttr(TAttribute<FText> S, EType Type, TAttribute<FSlateColor> Color, bool bWrap)
	{
		if (OnPaper())
		{
			const TAttribute<FSlateColor> Glass = Color;
			Color = TAttribute<FSlateColor>::CreateLambda([Glass]() { return FSlateColor(Surface(true, Glass.Get(FSlateColor(Fg)).GetSpecifiedColor())); });
		}
		return SNew(STextBlock).Text(S).Font(Font(Type)).ColorAndOpacity(Color).AutoWrapText(bWrap).LineBreakPolicy(LineBreaksFor(bWrap))
			.LineHeightPercentage(Type == EType::Body || Type == EType::Small ? 1.3f : 1.f);
	}

	TSharedRef<SWidget> Pill(const FString& S, bool bAccent)
	{
		return SNew(SBorder).BorderImage(Rounded(OnSurface(bAccent ? Accent : Raise), 11.f, OnSurface(bAccent ? Accent : Line), 1.f)).Padding(FMargin(10.f, 3.f))
			[ Text(S, EType::Label, bAccent ? AccentInk : Fg) ];
	}

	TSharedRef<SWidget> PanelBox(TSharedRef<SWidget> Content, FMargin Padding, float Radius)
	{
		// Built inside an FScopedPaper it is a sheet of chart paper.
		if (OnPaper()) return PaperSheet(Content, Padding, Radius, Paper, PaperLine);
		return SNew(SBorder).BorderImage(Rounded(IsLow() ? PanelSolid : Panel, Radius, OnSurface(Line), 1.f)).Padding(Padding)[ Content ];
	}

	TSharedRef<SWidget> PaperSheet(TSharedRef<SWidget> Content, FMargin Padding, float Radius, const FLinearColor& Fill, const FLinearColor& Outline)
	{
		const FSlateBrush* Grain = PaperGrain();
		if (!Grain) return SNew(SBorder).BorderImage(Rounded(Fill, Radius, Outline, 1.f)).Padding(Padding)[ Content ];
		// The grain is a square image: held inside the sheet's rounded corners by a third of the radius (at its few
		// percent the missing corner slivers do not show).
		return SNew(SOverlay)
			+ SOverlay::Slot()[ SNew(SBorder).BorderImage(Rounded(Fill, Radius, Outline, 1.f)) ]
			+ SOverlay::Slot().Padding(FMath::Max(1.f, Radius * 0.3f))[ SNew(SImage).Image(Grain).DesiredSizeOverride(FVector2D(1.0, 1.0)).Visibility(EVisibility::HitTestInvisible) ]	// or the sheet is never smaller than the 256 px tile (the title's Mode panel grew)
			+ SOverlay::Slot().Padding(Padding)[ Content ];
	}

	TArray<FPadGlyph> ParsePadGlyphs(const FString& Pad)
	{
		TArray<FPadGlyph> Out;
		TArray<FString> Tokens;
		Pad.ParseIntoArray(Tokens, TEXT(" / "), true);
		for (FString Token : Tokens)
		{
			Token.TrimStartAndEndInline();
			if (Token.IsEmpty()) continue;
			FPadGlyph G;
			G.Label = Token;
			// Arrows anywhere in the token are directions: on their own they are the D-pad, after a stick's letter the stick.
			uint8 Arms = 0;
			FString Rest;
			for (const TCHAR Ch : Token)
			{
				if (Ch == TCHAR(0x2191)) Arms |= 1;
				else if (Ch == TCHAR(0x2193)) Arms |= 2;
				else if (Ch == TCHAR(0x2190)) Arms |= 4;
				else if (Ch == TCHAR(0x2192)) Arms |= 8;
				else if (Ch == TCHAR(0x2195)) Arms |= 3;
				else if (Ch == TCHAR(0x2194)) Arms |= 12;
				else Rest.AppendChar(Ch);
			}
			Rest.TrimStartAndEndInline();
			const FString Up = Rest.ToUpper();
			if (Up == TEXT("A") || Up == TEXT("B") || Up == TEXT("X") || Up == TEXT("Y")) { G.Kind = EPadGlyph::Face; G.Label = Up; }
			else if (Up == TEXT("LB") || Up == TEXT("RB")) { G.Kind = EPadGlyph::Bumper; G.Label = Up; }
			else if (Up == TEXT("LT") || Up == TEXT("RT")) { G.Kind = EPadGlyph::Trigger; G.Label = Up; }
			else if (Up == TEXT("L3") || Up == TEXT("R3")) { G.Kind = EPadGlyph::StickClick; G.Label = Up.Left(1); }
			else if (Up == TEXT("L") || Up == TEXT("R") || Up == TEXT("L STICK") || Up == TEXT("R STICK")) { G.Kind = EPadGlyph::Stick; G.Label = Up.Left(1); G.Arms = Arms; }
			else if (Up == TEXT("D-PAD")) { G.Kind = EPadGlyph::Dpad; G.Label.Reset(); G.Arms = 15; }
			else if (Up.IsEmpty() && Arms != 0) { G.Kind = EPadGlyph::Dpad; G.Label.Reset(); G.Arms = Arms; }
			else if (Up == TEXT("VIEW")) { G.Kind = EPadGlyph::View; G.Label.Reset(); }
			else if (Up == TEXT("MENU")) { G.Kind = EPadGlyph::Menu; G.Label.Reset(); }
			Out.Add(G);
		}
		return Out;
	}

	float PadGlyphWidth(const FPadGlyph& Glyph)
	{
		switch (Glyph.Kind)
		{
		case EPadGlyph::Bumper: return 36.f;
		case EPadGlyph::Trigger: return 30.f;
		case EPadGlyph::View:
		case EPadGlyph::Menu: return 30.f;
		case EPadGlyph::Text: return 16.f + 8.5f * Glyph.Label.Len();
		default: return 24.f;
		}
	}

	namespace
	{
		// A box with a radius per corner (top left, top right, bottom right, bottom left): bumpers and triggers.
		const FSlateBrush* RoundedCorners(const FLinearColor& Fill, const FVector4& Radii, const FLinearColor& Outline, float OutlineWidth)
		{
			static TMap<FString, TUniquePtr<FSlateRoundedBoxBrush>> Cache;
			const FString Key = FString::Printf(TEXT("%s|%s|%s|%.1f"), *Fill.ToString(), *Radii.ToString(), *Outline.ToString(), OutlineWidth);
			if (TUniquePtr<FSlateRoundedBoxBrush>* Found = Cache.Find(Key)) return Found->Get();
			TUniquePtr<FSlateRoundedBoxBrush> B = MakeUnique<FSlateRoundedBoxBrush>(FSlateColor(Fill), Radii, FSlateColor(Outline), OutlineWidth);
			const FSlateBrush* Made = B.Get();
			Cache.Add(Key, MoveTemp(B));
			return Made;
		}

		/** A prompt's controller glyphs in a row. */
		class SPadGlyphs : public SLeafWidget
		{
		public:
			SLATE_BEGIN_ARGS(SPadGlyphs) {}
			SLATE_END_ARGS()
			void Construct(const FArguments&, const FString& Pad) { Glyphs = ParsePadGlyphs(Pad); }
			virtual FVector2D ComputeDesiredSize(float) const override
			{
				float W = 0.f;
				for (const FPadGlyph& G : Glyphs) W += PadGlyphWidth(G);
				return FVector2D(W + GlyphGap * FMath::Max(Glyphs.Num() - 1, 0), GlyphH);
			}
			virtual int32 OnPaint(const FPaintArgs&, const FGeometry& Geo, const FSlateRect&, FSlateWindowElementList& Out, int32 Layer, const FWidgetStyle& Style, bool) const override
			{
				const FLinearColor Tint = Style.GetColorAndOpacityTint();
				const float Top = (float(Geo.GetLocalSize().Y) - GlyphH) * 0.5f;
				float X = 0.f;
				for (const FPadGlyph& G : Glyphs)
				{
					const float W = PadGlyphWidth(G);
					PaintOne(Out, Layer, Geo, G, FVector2f(X, Top), W, Tint);
					X += W + GlyphGap;
				}
				return Layer + 3;
			}

		private:
			static constexpr float GlyphH = 24.f;
			static constexpr float GlyphGap = 5.f;

			static void Fill(FSlateWindowElementList& Out, int32 Layer, const FGeometry& Geo, FVector2f At, FVector2f Size, const FSlateBrush* Brush, const FLinearColor& Tint)
			{
				FSlateDrawElement::MakeBox(Out, Layer, Geo.ToPaintGeometry(Size, FSlateLayoutTransform(At)), Brush, ESlateDrawEffect::None, Tint * Brush->TintColor.GetSpecifiedColor());
			}
			static void Stroke(FSlateWindowElementList& Out, int32 Layer, const FGeometry& Geo, const TArray<FVector2f>& Points, const FLinearColor& Colour, float Thickness)
			{
				FSlateDrawElement::MakeLines(Out, Layer, Geo.ToPaintGeometry(), Points, ESlateDrawEffect::None, Colour, true, Thickness);
			}
			static void Letters(FSlateWindowElementList& Out, int32 Layer, const FGeometry& Geo, const FString& Str, FVector2f Centre, float Points, const FLinearColor& Colour)
			{
				FSlateFontInfo F = Font(EType::Label);
				F.Size = static_cast<decltype(F.Size)>(Points);
				F.LetterSpacing = 0;
				FVector2f Size(Points * 0.62f * Str.Len(), Points * 1.35f);
				if (FSlateApplication::IsInitialized()) Size = FVector2f(FSlateApplication::Get().GetRenderer()->GetFontMeasureService()->Measure(Str, F));
				FSlateDrawElement::MakeText(Out, Layer, Geo.ToPaintGeometry(Size + FVector2f(2.f, 2.f), FSlateLayoutTransform(Centre - Size * 0.5f)), Str, F, ESlateDrawEffect::None, Colour);
			}

			static void PaintOne(FSlateWindowElementList& Out, int32 Layer, const FGeometry& Geo, const FPadGlyph& G, FVector2f At, float W, const FLinearColor& Tint)
			{
				const FLinearColor Body = Raise, Edge = Hex(0x8FA1AD), Lit = Fg, Unlit = Hex(0x5A6B77);
				const FVector2f Mid = At + FVector2f(W * 0.5f, GlyphH * 0.5f);
				switch (G.Kind)
				{
				case EPadGlyph::Face:
				{
					// The pad's own colours, softened, as the ring: the disc stays ink so the letter reads.
					const FLinearColor Ring = G.Label == TEXT("A") ? Hex(0x58B87A) : G.Label == TEXT("B") ? Hex(0xE2685E) : G.Label == TEXT("X") ? Hex(0x5B9BE0) : Hex(0xE2B94A);
					Fill(Out, Layer, Geo, At, FVector2f(GlyphH, GlyphH), Rounded(Body, GlyphH * 0.5f, Ring, 2.f), Tint);
					Letters(Out, Layer + 1, Geo, G.Label, Mid, 10.f, Tint * Lit);
					break;
				}
				case EPadGlyph::Bumper:
					Fill(Out, Layer, Geo, At + FVector2f(0.f, 3.f), FVector2f(W, 18.f), RoundedCorners(Body, FVector4(9.f, 9.f, 3.f, 3.f), Edge, 1.5f), Tint);
					Letters(Out, Layer + 1, Geo, G.Label, Mid, 9.f, Tint * Lit);
					break;
				case EPadGlyph::Trigger:
					Fill(Out, Layer, Geo, At, FVector2f(W, GlyphH), RoundedCorners(Body, FVector4(4.f, 4.f, 11.f, 11.f), Edge, 1.5f), Tint);
					Letters(Out, Layer + 1, Geo, G.Label, Mid + FVector2f(0.f, 0.5f), 9.f, Tint * Lit);
					break;
				case EPadGlyph::Dpad:
				{
					const float Arm = 8.f;
					const FSlateBrush* Bar = Rounded(Unlit, 2.f);
					Fill(Out, Layer, Geo, FVector2f(Mid.X - Arm * 0.5f, At.Y), FVector2f(Arm, GlyphH), Bar, Tint);
					Fill(Out, Layer, Geo, FVector2f(At.X, Mid.Y - Arm * 0.5f), FVector2f(GlyphH, Arm), Bar, Tint);
					const FSlateBrush* On = Rounded(Lit, 2.f);
					if (G.Arms & 1) Fill(Out, Layer + 1, Geo, FVector2f(Mid.X - Arm * 0.5f, At.Y), FVector2f(Arm, Arm), On, Tint);
					if (G.Arms & 2) Fill(Out, Layer + 1, Geo, FVector2f(Mid.X - Arm * 0.5f, At.Y + GlyphH - Arm), FVector2f(Arm, Arm), On, Tint);
					if (G.Arms & 4) Fill(Out, Layer + 1, Geo, FVector2f(At.X, Mid.Y - Arm * 0.5f), FVector2f(Arm, Arm), On, Tint);
					if (G.Arms & 8) Fill(Out, Layer + 1, Geo, FVector2f(At.X + GlyphH - Arm, Mid.Y - Arm * 0.5f), FVector2f(Arm, Arm), On, Tint);
					break;
				}
				case EPadGlyph::Stick:
				case EPadGlyph::StickClick:
				{
					const bool bClick = G.Kind == EPadGlyph::StickClick;
					// With directions the ring makes room for the chevrons above and below (or beside).
					const float Ring = G.Arms != 0 ? 16.f : GlyphH;
					Fill(Out, Layer, Geo, Mid - FVector2f(Ring, Ring) * 0.5f, FVector2f(Ring, Ring), Rounded(FLinearColor::Transparent, Ring * 0.5f, G.Arms != 0 ? Lit : Edge, 1.5f), Tint);	// the small ring with chevrons was the faintest glyph
					const float Cap = Ring - 8.f;
					Fill(Out, Layer + 1, Geo, Mid - FVector2f(Cap, Cap) * 0.5f, FVector2f(Cap, Cap), Rounded(bClick ? Lit : Body, Cap * 0.5f, bClick ? Lit : Edge, 1.f), Tint);
					if (G.Arms == 0) Letters(Out, Layer + 2, Geo, G.Label, Mid, 8.f, Tint * (bClick ? Ink : Lit));
					const float R = Ring * 0.5f + 1.5f, C = 2.5f;
					if (G.Arms & 1) Stroke(Out, Layer + 2, Geo, { Mid + FVector2f(-C, -R), Mid + FVector2f(0.f, -R - C), Mid + FVector2f(C, -R) }, Tint * Lit, 2.f);
					if (G.Arms & 2) Stroke(Out, Layer + 2, Geo, { Mid + FVector2f(-C, R), Mid + FVector2f(0.f, R + C), Mid + FVector2f(C, R) }, Tint * Lit, 2.f);
					if (G.Arms & 4) Stroke(Out, Layer + 2, Geo, { Mid + FVector2f(-R, -C), Mid + FVector2f(-R - C, 0.f), Mid + FVector2f(-R, C) }, Tint * Lit, 1.5f);
					if (G.Arms & 8) Stroke(Out, Layer + 2, Geo, { Mid + FVector2f(R, -C), Mid + FVector2f(R + C, 0.f), Mid + FVector2f(R, C) }, Tint * Lit, 1.5f);
					break;
				}
				case EPadGlyph::View:
					Fill(Out, Layer, Geo, At + FVector2f(0.f, 3.f), FVector2f(W, 18.f), Rounded(Body, 9.f, Edge, 1.5f), Tint);
					// Two overlapping windows.
					Stroke(Out, Layer + 1, Geo, { Mid + FVector2f(-5.f, -1.f), Mid + FVector2f(-5.f, -4.f), Mid + FVector2f(2.f, -4.f), Mid + FVector2f(2.f, -1.f) }, Tint * Lit, 1.2f);
					Stroke(Out, Layer + 1, Geo, { Mid + FVector2f(-2.f, -1.f), Mid + FVector2f(5.f, -1.f), Mid + FVector2f(5.f, 4.f), Mid + FVector2f(-2.f, 4.f), Mid + FVector2f(-2.f, -1.f) }, Tint * Lit, 1.2f);
					break;
				case EPadGlyph::Menu:
					Fill(Out, Layer, Geo, At + FVector2f(0.f, 3.f), FVector2f(W, 18.f), Rounded(Body, 9.f, Edge, 1.5f), Tint);
					for (int32 I = -1; I <= 1; ++I) Stroke(Out, Layer + 1, Geo, { Mid + FVector2f(-5.f, I * 3.5f), Mid + FVector2f(5.f, I * 3.5f) }, Tint * Lit, 1.3f);
					break;
				default:
					Fill(Out, Layer, Geo, At + FVector2f(0.f, 2.f), FVector2f(W, 20.f), Rounded(Body, 10.f, Edge, 1.f), Tint);
					Letters(Out, Layer + 1, Geo, G.Label, Mid, 10.f, Tint * Lit);
					break;
				}
			}

			TArray<FPadGlyph> Glyphs;
		};
	}

	TSharedRef<SWidget> KeyCap(const FString& Keyboard, const FString& Pad)
	{
		const bool bPaper = OnPaper();
		// The keyboard's cap and the controller's glyphs, whichever device was used last.
		return SNew(SOverlay)
			+ SOverlay::Slot().VAlign(VAlign_Center)
			[
				SNew(SBorder).BorderImage(Rounded(Surface(bPaper, Raise), 5.f, Surface(bPaper, Line), 1.f)).Padding(FMargin(8.f, 2.f)).VAlign(VAlign_Center)
					.Visibility_Lambda([]() { return UsingGamepad() ? EVisibility::Collapsed : EVisibility::Visible; })
				[ SNew(STextBlock).Text(FText::FromString(Keyboard)).Font(Font(EType::Label)).ColorAndOpacity(FSlateColor(Surface(bPaper, Fg))) ]
			]
			+ SOverlay::Slot().VAlign(VAlign_Center)
			[
				SNew(SPadGlyphs, Pad).Visibility_Lambda([]() { return UsingGamepad() ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
			];
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
					+ SVerticalBox::Slot().AutoHeight()[ SNew(SBox).WidthOverride(122.f).HeightOverride(5.f)
						[ SNew(SBorder).BorderImage(Rounded(bCur ? Accent : (bDone ? Fg : Muted.CopyWithNewOpacity(0.5f)), 2.f)) ] ]
					+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 6.f, 0.f, 0.f)
						[ Text(FString::Printf(TEXT("%d %s"), I + 1, Names[I]), EType::Label, bCur ? Accent : (bDone ? Fg : Muted)) ]
				];
			}
		}
		return SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().FillWidth(1.f).VAlign(VAlign_Bottom)
			[
				SNew(SVerticalBox)
				+ SVerticalBox::Slot().AutoHeight()[ TextOverScene(Eyebrow, EType::Eyebrow, Fg) ]   // (the accent is lost on a bright cloud: chart paper with its shadow reads on anything)
				+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 4.f, 0.f, 0.f)[ TextOverScene(Title, EType::ScreenTitle, Fg) ]
			]
			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Bottom).Padding(0.f, 0.f, 0.f, 14.f)
			// (The steps lie on their own strip of glass: over a bright sky the thin bars were lost.)
			[ Step > 0 ? PanelBox(Steps, FMargin(10.f, 10.f, 10.f, 8.f), RadiusButton) : TSharedRef<SWidget>(Steps) ];
	}

	TSharedRef<SSailButton> ActionButton(const FString& Label, FSimpleDelegate OnClicked, bool bPrimary)
	{
		return SNew(SSailButton).Look(bPrimary ? EButtonLook::Primary : EButtonLook::Secondary).OnClicked(OnClicked).Padding(FMargin(28.f, 14.f))
			[ SNew(SBox).HAlign(HAlign_Center)[ Text(Label, EType::Button, bPrimary ? AccentInk : Fg) ] ];
	}

	TSharedRef<SSailButton> MenuRow(const FString& Label, const FString& Sub, FSimpleDelegate OnClicked, bool bEnabled, float PadY)
	{
		// The text asks its own row whether it has the focus (the row is made after its text, so through a holder).
		const TSharedRef<TWeakPtr<SSailButton>> Self = MakeShared<TWeakPtr<SSailButton>>();
		auto Colour = [Self](const FLinearColor& Off, const FLinearColor& On)
		{
			return TAttribute<FSlateColor>::CreateLambda([Self, Off, On]()
			{
				const TSharedPtr<SSailButton> Row = Self->Pin();
				return FSlateColor(Row.IsValid() && Row->IsFocusedNow() ? On : Off);
			});
		};
		// Off the paper label the text lies on the scene: an ink shadow keeps its edge (none on the label itself).
		const TAttribute<FLinearColor> Shadow = TAttribute<FLinearColor>::CreateLambda([Self]()
		{
			const TSharedPtr<SSailButton> Held = Self->Pin();
			return Held.IsValid() && Held->IsFocusedNow() ? FLinearColor::Transparent : Ink.CopyWithNewOpacity(0.7f);
		});
		const TSharedRef<SSailButton> Row = SNew(SSailButton).Look(EButtonLook::MenuRow).OnClicked(OnClicked).IsEnabled(bEnabled).Padding(FMargin(32.f, PadY, 18.f, PadY))
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().FillWidth(1.f).VAlign(VAlign_Center)[ SNew(STextBlock).Text(Txt(Label, EType::MenuItem)).Font(Font(EType::MenuItem)).ColorAndOpacity(Colour(bEnabled ? Fg : Muted, PaperInk)).ShadowOffset(FVector2D(1.f, 1.5f)).ShadowColorAndOpacity(Shadow) ]
			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)[ SNew(STextBlock).Text(Txt(Sub, EType::Small)).Font(Font(EType::Small)).ColorAndOpacity(Colour(bEnabled ? Fg.CopyWithNewOpacity(0.85f) : Muted, PaperMuted)).ShadowOffset(FVector2D(1.f, 1.5f)).ShadowColorAndOpacity(Shadow) ]
		];
		*Self = Row;
		return Row;
	}
}

// ---------------------------------------------------------------- SSailButton

void SSailButton::Construct(const FArguments& A)
{
	Look = A._Look;
	bPaper = SailUI::OnPaper();
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
	if (IsEnabledNow() && !HasKeyboardFocus() && SailUI::MouseIsActive()) SailUI::FocusByHover(SharedThis(this));
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
	if (!bOn) S.BlendColorAndOpacityTint(FLinearColor(1, 1, 1, 0.62f));   // was 0.45: a locked card's reason has to read
	const FLinearColor T = S.GetColorAndOpacityTint();
	// On a paper sheet each glass token is drawn as its paper twin.
	auto C = [this](const FLinearColor& Glass) { return SailUI::Surface(bPaper, Glass); };
	switch (Look)
	{
	case SailUI::EButtonLook::Card:
		// A locked card keeps its whole panel (only what is on it is dimmed): at the dimmed tint the glass went thin and
		// the scene showed through its text.
		SailUI::Box(Out, Layer, G, FVector2D::ZeroVector, SailUI::Rounded(bPaper ? SailUI::Paper : (SailUI::IsLow() ? SailUI::PanelSolid : SailUI::Panel), SailUI::RadiusCard, C(bSel ? SailUI::Selected : SailUI::Line), bSel ? 1.5f : 1.f), Style.GetColorAndOpacityTint());
		break;
	case SailUI::EButtonLook::Pin:
		// Ink on the paper map with a paper ring; the chosen pin is the accent with an ink ring (UI overhaul phase 3:
		// the chart's magenta stays on the chart, and a paper pin was lost on the paper-coloured land).
		SailUI::Box(Out, Layer, G, FVector2D::ZeroVector, SailUI::Rounded(bSel ? SailUI::Accent : SailUI::Ink, FMath::RoundToFloat(G.GetLocalSize().Y * 0.5f), bSel ? SailUI::Ink : SailUI::Fg, 2.f), T);
		break;
	case SailUI::EButtonLook::MenuRow:
		if (bFocus)
		{
			// The paper label under the focused row, and the accent diamond at its head.
			SailUI::Box(Out, Layer, G, FVector2D::ZeroVector, SailUI::Rounded(SailUI::Paper, 2.f), T);
			const float Cy = float(G.GetLocalSize().Y) * 0.5f;
			FSlateDrawElement::MakeLines(Out, Layer + 1, G.ToPaintGeometry(), { FVector2f(10.f, Cy), FVector2f(16.f, Cy - 6.f), FVector2f(22.f, Cy), FVector2f(16.f, Cy + 6.f), FVector2f(10.f, Cy) },
				ESlateDrawEffect::None, SailUI::AccentDeep * T, true, 3.f);
		}
		break;
	case SailUI::EButtonLook::MenuItem:
		if (bFocus)
		{
			SailUI::Box(Out, Layer, G, FVector2D::ZeroVector, SailUI::Rounded(C(SailUI::Accent).CopyWithNewOpacity(0.16f), 3.f), T);
			FSlateDrawElement::MakeBox(Out, Layer + 1, G.ToPaintGeometry(FVector2f(4.f, G.GetLocalSize().Y), FSlateLayoutTransform()), SailUI::Rounded(C(SailUI::Accent), 1.f), ESlateDrawEffect::None, T * C(SailUI::Accent));
		}
		break;
	case SailUI::EButtonLook::Primary:
		SailUI::Box(Out, Layer, G, FVector2D::ZeroVector, SailUI::Rounded(C(SailUI::Accent), SailUI::RadiusButton), T);
		break;
	case SailUI::EButtonLook::Secondary:
		SailUI::Box(Out, Layer, G, FVector2D::ZeroVector, SailUI::Rounded(C(SailUI::Raise), SailUI::RadiusButton, C(SailUI::Line), 1.f), T);
		break;
	case SailUI::EButtonLook::Chip:
		SailUI::Box(Out, Layer, G, FVector2D::ZeroVector, SailUI::Rounded(C(bSel ? SailUI::Fg : SailUI::Raise), SailUI::RadiusButton, C(SailUI::Line), 1.f), T);
		break;
	}
	int32 Max = SCompoundWidget::OnPaint(Args, G, Culling, Out, Layer + 2, S, bParentEnabled);
	if (bSel && Look == SailUI::EButtonLook::Card)
	{
		// The tick in the top-right corner of a chosen card (drawn: the fonts have no check mark).
		const FVector2D Sz = G.GetLocalSize();
		const FVector2f O(Sz.X - 30.f, 14.f);
		FSlateDrawElement::MakeLines(Out, Max + 1, G.ToPaintGeometry(), { O + FVector2f(0.f, 7.f), O + FVector2f(5.f, 12.f), O + FVector2f(15.f, 0.f) },
			ESlateDrawEffect::None, C(SailUI::Accent) * T, true, 3.f);
	}
	if (bFocus && Look != SailUI::EButtonLook::MenuItem && Look != SailUI::EButtonLook::MenuRow)
	{
		// Focus: a 3 px accent ring and a soft glow (paper on the accent button).
		const float R = Look == SailUI::EButtonLook::Pin ? FMath::RoundToFloat(G.GetLocalSize().Y * 0.5f) : (Look == SailUI::EButtonLook::Card ? SailUI::RadiusCard : SailUI::RadiusButton);
		const FLinearColor Ring = C(Look == SailUI::EButtonLook::Primary ? SailUI::Fg : SailUI::Accent);
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
	bPaper = SailUI::OnPaper();
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
			[ SNew(STextBlock).Text_Lambda([ValueText]() { return FText::FromString(ValueText.Get(FString())); }).Font(SailUI::Font(SailUI::EType::Value)).ColorAndOpacity(SailUI::OnSurface(SailUI::Fg)) ]
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
	if (Enabled.Get(true) && !HasKeyboardFocus() && SailUI::MouseIsActive()) SailUI::FocusByHover(SharedThis(this));
}

int32 SSailSlider::OnPaint(const FPaintArgs& Args, const FGeometry& G, const FSlateRect& Culling, FSlateWindowElementList& Out, int32 Layer,
	const FWidgetStyle& Style, bool bParentEnabled) const
{
	FWidgetStyle S = Style;
	if (!Enabled.Get(true)) S.BlendColorAndOpacityTint(FLinearColor(1, 1, 1, 0.4f));
	// (On a paper sheet the row is a ruled cell of the sheet, not a panel of its own.)
	SailUI::Box(Out, Layer, G, FVector2D::ZeroVector, SailUI::Rounded(bPaper ? FLinearColor::Transparent : (SailUI::IsLow() ? SailUI::PanelSolid : SailUI::Panel), SailUI::RadiusButton, SailUI::Surface(bPaper, SailUI::Line), 1.f), S.GetColorAndOpacityTint());
	int32 Top = SCompoundWidget::OnPaint(Args, G, Culling, Out, Layer + 1, S, bParentEnabled);
	if (HasKeyboardFocus())
	{
		SailUI::Box(Out, Top + 1, G, FVector2D(-2.f), SailUI::Rounded(FLinearColor::Transparent, SailUI::RadiusButton + 2.f, SailUI::Surface(bPaper, SailUI::Accent), 3.f));
		++Top;
	}
	return Top + 1;
}

// ---------------------------------------------------------------- SSailChoice

void SSailChoice::Construct(const FArguments& A)
{
	Options = A._Options; Index = A._Index; Enabled = A._IsEnabled; OnChanged = A._OnChanged;
	bPaper = SailUI::OnPaper();
	const bool bP = bPaper;
	SetTag(FName(*A._Label));   // names the choice in the UI script's log (every Seg choice has the same source line)
	// The chips take the width the row gives them and wrap (right-aligned) when it's too narrow; six or more sit a little
	// tighter. (The Sky row's six ran past its panel over the next column at 1440x1080.)
	const bool bMany = Options.Num() >= 6;
	TSharedRef<SWrapBox> Chips = SNew(SWrapBox).UseAllottedSize(true).HAlign(HAlign_Right).InnerSlotPadding(FVector2D(0.f, 6.f));
	for (int32 I = 0; I < Options.Num(); ++I)
	{
		const TAttribute<int32> Idx = Index;
		Chips->AddSlot().Padding(bMany ? 3.f : 4.f, 0.f)
		[
			SNew(SBorder).Padding(FMargin(bMany ? 8.f : 10.f, 4.f))
			.BorderImage_Lambda([Idx, I, bP]() { return SailUI::Rounded(SailUI::Surface(bP, Idx.Get(0) == I ? SailUI::Fg : SailUI::Raise), SailUI::RadiusButton, SailUI::Surface(bP, SailUI::Line), 1.f); })
			.OnMouseButtonDown_Lambda([this, I](const FGeometry&, const FPointerEvent&) { if (Enabled.Get(true)) OnChanged.ExecuteIfBound(I); return FReply::Handled(); })
			[
				SNew(STextBlock).Text(FText::FromString(Options[I])).Font(SailUI::Font(SailUI::EType::Ui))
				.ColorAndOpacity_Lambda([Idx, I, bP]() { return FSlateColor(SailUI::Surface(bP, Idx.Get(0) == I ? SailUI::Ink : SailUI::Fg)); })
			]
		];
	}
	TSharedRef<SVerticalBox> Col = SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight()
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().FillWidth(0.3f).VAlign(VAlign_Center)[ SailUI::Text(A._Label, SailUI::EType::Ui, SailUI::Fg) ]
			+ SHorizontalBox::Slot().FillWidth(0.7f).HAlign(HAlign_Fill).VAlign(VAlign_Center)[ Chips ]
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
	if (Enabled.Get(true) && !HasKeyboardFocus() && SailUI::MouseIsActive()) SailUI::FocusByHover(SharedThis(this));
}

int32 SSailChoice::OnPaint(const FPaintArgs& Args, const FGeometry& G, const FSlateRect& Culling, FSlateWindowElementList& Out, int32 Layer,
	const FWidgetStyle& Style, bool bParentEnabled) const
{
	FWidgetStyle S = Style;
	if (!Enabled.Get(true)) S.BlendColorAndOpacityTint(FLinearColor(1, 1, 1, 0.4f));
	// (On a paper sheet the row is a ruled cell of the sheet, not a panel of its own.)
	SailUI::Box(Out, Layer, G, FVector2D::ZeroVector, SailUI::Rounded(bPaper ? FLinearColor::Transparent : (SailUI::IsLow() ? SailUI::PanelSolid : SailUI::Panel), SailUI::RadiusButton, SailUI::Surface(bPaper, SailUI::Line), 1.f), S.GetColorAndOpacityTint());
	int32 Top = SCompoundWidget::OnPaint(Args, G, Culling, Out, Layer + 1, S, bParentEnabled);
	if (HasKeyboardFocus())
	{
		SailUI::Box(Out, Top + 1, G, FVector2D(-2.f), SailUI::Rounded(FLinearColor::Transparent, SailUI::RadiusButton + 2.f, SailUI::Surface(bPaper, SailUI::Accent), 3.f));
		++Top;
	}
	return Top + 1;
}
