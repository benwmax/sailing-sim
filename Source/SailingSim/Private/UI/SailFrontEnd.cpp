#include "UI/SailFrontEnd.h"
#include "BenchRunner.h"
#include "SailingSim.h"
#include "UI/SailWidgets.h"
#include "UI/SailGraphicsRows.h"
#include "GalleryStage.h"
#include "UI/SailCatalog.h"
#include "UI/SailHud.h"
#include "Engine/Engine.h"
#include "GameFramework/GameUserSettings.h"
#include "Engine/GameViewportClient.h"
#include "Widgets/SWindow.h"
#include "SailboatPawn.h"
#include "SailingGameMode.h"
#include "SailingSettings.h"
#include "SailingBindings.h"
#include "Drills.h"
#include "Learning.h"
#include "Career.h"
#include "SailSave.h"
#include "Engine/Texture2D.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Rendering/DrawElements.h"
#include "Styling/SlateBrush.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SConstraintCanvas.h"
#include "Widgets/Layout/SGridPanel.h"
#include "Widgets/Layout/SScaleBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SSpacer.h"
#include "Widgets/Layout/SUniformGridPanel.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SLeafWidget.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"

namespace SailFrontEndImpl
{
	/** "Oct 18" (FDateTime::ToString has no month-name format: %b printed the letter). */
	FString ShortDate(const FDateTime& T, bool bYear = false)
	{
		static const TCHAR* Months[] = { TEXT("Jan"), TEXT("Feb"), TEXT("Mar"), TEXT("Apr"), TEXT("May"), TEXT("Jun"), TEXT("Jul"), TEXT("Aug"), TEXT("Sep"), TEXT("Oct"), TEXT("Nov"), TEXT("Dec") };
		const FString D = FString::Printf(TEXT("%s %d"), Months[FMath::Clamp(T.GetMonth(), 1, 12) - 1], T.GetDay());
		return bYear ? FString::Printf(TEXT("%s, %d"), *D, T.GetYear()) : D;
	}
	/** The Sky row's order (Rain sits after Overcast; ESailSky appends it last so saves and int uses keep their meaning). */
	const TArray<ESailSky> SkyRowOrder = { ESailSky::Clear, ESailSky::Fair, ESailSky::Overcast, ESailSky::Rain, ESailSky::Storms, ESailSky::Fog };
	using namespace SailUI;
	using Prompt = TTuple<FString, FString, FString>;

	/** A texture as a Slate brush (kept alive with the brush). */
	TSharedPtr<FSlateBrush> TextureBrush(const FString& Path)
	{
		UTexture2D* Tex = SailUI::KeptTexture(Path);
		TSharedPtr<FSlateBrush> B = MakeShared<FSlateBrush>();
		if (Tex)
		{
			B->SetResourceObject(Tex);
			B->ImageSize = FVector2D(Tex->GetSizeX(), Tex->GetSizeY());
		}
		else
		{
			B->TintColor = FSlateColor(Raise);
		}
		return B;
	}

	/** The menus' backdrop: a left-to-right Ink gradient so text reads on any sky (5.1), or an even dim. */
	class SBackdrop : public SLeafWidget
	{
	public:
		SLATE_BEGIN_ARGS(SBackdrop) {}
			SLATE_ATTRIBUTE(float, LeftAlpha)
			SLATE_ATTRIBUTE(float, RightAlpha)
			/** The showroom's look (the Boat screen): no left-heavy wash. */
			SLATE_ATTRIBUTE(bool, Showroom)
			/** A dip to dark over the whole screen (0..1): the boat swap's cover. */
			SLATE_ATTRIBUTE(float, Dip)
			/** The showroom's left fade ends here, a share of the width: the left panel's right edge. */
			SLATE_ATTRIBUTE(float, FadeEnd)
		SLATE_END_ARGS()
		void Construct(const FArguments& A) { L = A._LeftAlpha; R = A._RightAlpha; Showroom = A._Showroom; Dip = A._Dip; FadeEnd = A._FadeEnd; }
		virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D(8, 8); }
		virtual int32 OnPaint(const FPaintArgs&, const FGeometry& G, const FSlateRect&, FSlateWindowElementList& Out, int32 Layer, const FWidgetStyle&, bool) const override
		{
			const FVector2f S(G.GetLocalSize());
			if (Showroom.Get(false))
			{
				// Inputs/ui-showroom/brief.md section 2: soft vignettes top and bottom so the boat stays bright, and a light
				// fade behind the left column that ends at its right edge (Bean, Oct 27: never into the boat's side), 460 px
				// of 1440, with the width.
				auto Band = [&](FVector2f At, FVector2f Size, float A0, float A1, EOrientation O)
				{
					TArray<FSlateGradientStop> St;
					St.Add(FSlateGradientStop(FVector2f(0.f, 0.f), Ink.CopyWithNewOpacity(A0)));
					St.Add(FSlateGradientStop(O == Orient_Vertical ? FVector2f(Size.X, 0.f) : FVector2f(0.f, Size.Y), Ink.CopyWithNewOpacity(A1)));
					FSlateDrawElement::MakeGradient(Out, Layer, G.ToPaintGeometry(Size, FSlateLayoutTransform(At)), St, O);
				};
				Band(FVector2f(0.f, 0.f), FVector2f(S.X, S.Y * 0.16f), 0.55f, 0.f, Orient_Horizontal);
				Band(FVector2f(0.f, S.Y * 0.72f), FVector2f(S.X, S.Y * 0.28f), 0.f, 0.7f, Orient_Horizontal);
				Band(FVector2f(0.f, 0.f), FVector2f(S.X * FadeEnd.Get(460.f / 1440.f), S.Y), 0.45f, 0.f, Orient_Vertical);
			}
			else
			{
				TArray<FSlateGradientStop> Stops;
			Stops.Add(FSlateGradientStop(FVector2f(0.f, 0.f), Ink.CopyWithNewOpacity(L.Get(0.86f))));
			Stops.Add(FSlateGradientStop(FVector2f(G.GetLocalSize().X * 0.55f, 0.f), Ink.CopyWithNewOpacity(FMath::Lerp(L.Get(0.86f), R.Get(0.15f), 0.6f))));
			Stops.Add(FSlateGradientStop(FVector2f(G.GetLocalSize().X, 0.f), Ink.CopyWithNewOpacity(R.Get(0.15f))));
				FSlateDrawElement::MakeGradient(Out, Layer, G.ToPaintGeometry(), Stops, Orient_Vertical);
			}
			if (const float D = Dip.Get(0.f); D > 0.f) FSlateDrawElement::MakeBox(Out, Layer + 1, G.ToPaintGeometry(), Rounded(Ink, 0.f), ESlateDrawEffect::None, Ink.CopyWithNewOpacity(D));
			return Layer + 1;
		}
	private:
		TAttribute<float> L, R, Dip, FadeEnd;
		TAttribute<bool> Showroom;
	};

	/** A boat's silhouette for the cards (hull, rig and sails from its type), drawn rather than imported. */
	class SBoatIcon : public SLeafWidget
	{
	public:
		SLATE_BEGIN_ARGS(SBoatIcon) : _Type(0) {}
			SLATE_ARGUMENT(int32, Type)
		SLATE_END_ARGS()
		void Construct(const FArguments& A) { Type = A._Type; }
		virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D(200, 84); }
		virtual int32 OnPaint(const FPaintArgs&, const FGeometry& G, const FSlateRect&, FSlateWindowElementList& Out, int32 Layer, const FWidgetStyle& Style, bool) const override
		{
			const FVector2D S = G.GetLocalSize();
			const float Cx = S.X * 0.5f, Base = S.Y * 0.78f;
			// Per type: hull length, mast height and sail shape factors (relative), multihull flag.
			struct FShape { float Hull, Mast, Main, Jib; bool bMulti, bLateen, bCabin; };
			static const FShape Shapes[] = { { 0.62f, 0.62f, 0.32f, 0.22f, false, false, false }, { 0.42f, 0.42f, 0.36f, 0.f, false, true, false },
				{ 0.44f, 0.56f, 0.30f, 0.f, false, false, false }, { 0.58f, 0.55f, 0.28f, 0.22f, false, false, true }, { 0.70f, 0.70f, 0.30f, 0.28f, false, false, true },
				{ 0.52f, 0.62f, 0.30f, 0.16f, true, false, false }, { 0.70f, 0.70f, 0.30f, 0.24f, true, false, true }, { 0.80f, 0.68f, 0.30f, 0.26f, true, false, true } };
			const FShape& F = Shapes[FMath::Clamp(Type, 0, 7)];
			auto DrawLine = [&](TArray<FVector2f> P, const FLinearColor& C, float W)
			{
				FSlateDrawElement::MakeLines(Out, Layer + 1, G.ToPaintGeometry(), P, ESlateDrawEffect::None, C * Style.GetColorAndOpacityTint(), true, W);
			};
			auto Tri = [&](FVector2f A, FVector2f B, FVector2f C, const FLinearColor& Col)
			{
				// Filled by stacked lines (Slate has no polygon fill without a brush): dense horizontal hatching.
				const float Y0 = FMath::Min3(A.Y, B.Y, C.Y), Y1 = FMath::Max3(A.Y, B.Y, C.Y);
				for (float Y = Y0; Y <= Y1; Y += 1.f)
				{
					float Xs[3]; int32 N = 0;
					const FVector2f E[3][2] = { { A, B }, { B, C }, { C, A } };
					for (const auto& Ed : E)
					{
						const FVector2f P = Ed[0], Q = Ed[1];
						if ((Y >= FMath::Min(P.Y, Q.Y)) && (Y <= FMath::Max(P.Y, Q.Y)) && P.Y != Q.Y && N < 3) Xs[N++] = P.X + (Y - P.Y) / (Q.Y - P.Y) * (Q.X - P.X);
					}
					if (N >= 2) DrawLine({ FVector2f(FMath::Min(Xs[0], Xs[1]), Y), FVector2f(FMath::Max(Xs[0], Xs[1]), Y) }, Col, 1.2f);
				}
			};
			const float HL = S.X * F.Hull, MastH = S.Y * F.Mast, MastX = Cx + HL * 0.05f;
			const FLinearColor HullC = Hex(0x6E8798), SailC = Hex(0xEAF0F2), SailB = Hex(0xC9D3D8);
			// Hull (or hulls), a cabin, the waterline.
			Tri(FVector2f(Cx - HL * 0.5f, Base - 6.f), FVector2f(Cx + HL * 0.5f, Base - 6.f), FVector2f(Cx - HL * 0.42f, Base + 4.f), HullC);
			Tri(FVector2f(Cx + HL * 0.5f, Base - 6.f), FVector2f(Cx - HL * 0.42f, Base + 4.f), FVector2f(Cx + HL * 0.38f, Base + 4.f), HullC);
			if (F.bCabin) Tri(FVector2f(Cx - HL * 0.2f, Base - 6.f), FVector2f(Cx + HL * 0.1f, Base - 6.f), FVector2f(Cx - HL * 0.12f, Base - 13.f), HullC);
			DrawLine({ FVector2f(Cx - S.X * 0.46f, Base + 6.f), FVector2f(Cx + S.X * 0.46f, Base + 6.f) }, Hex(0x3C5F78), 2.f);
			if (F.bMulti) DrawLine({ FVector2f(Cx - HL * 0.45f, Base + 2.f), FVector2f(Cx + HL * 0.45f, Base + 2.f) }, HullC, 3.f);
			if (F.bLateen)
			{
				Tri(FVector2f(Cx - HL * 0.35f, Base - 10.f), FVector2f(Cx + HL * 0.40f, Base - MastH), FVector2f(Cx + HL * 0.42f, Base - 12.f), SailC);
				return Layer + 1;
			}
			DrawLine({ FVector2f(MastX, Base - 6.f), FVector2f(MastX, Base - MastH) }, Hex(0x9AA9B3), 1.5f);
			Tri(FVector2f(MastX - 2.f, Base - MastH + 2.f), FVector2f(MastX - 2.f, Base - 12.f), FVector2f(MastX - HL * F.Main * 1.4f, Base - 12.f), SailC);
			if (F.Jib > 0.f) Tri(FVector2f(MastX + 3.f, Base - MastH * 0.85f), FVector2f(MastX + 3.f, Base - 10.f), FVector2f(MastX + HL * F.Jib * 1.6f, Base - 10.f), SailB);
			return Layer + 1;
		}
	private:
		int32 Type = 0;
	};

	/** The wind dial (5.5): Left/Right turn it 5 degrees, the mouse sets it; shows where the wind comes from. */
	class SWindDial : public SLeafWidget
	{
	public:
		SLATE_BEGIN_ARGS(SWindDial) {}
			SLATE_ATTRIBUTE(float, Degrees)
			SLATE_EVENT(TDelegate<void(float)>, OnChanged)
		SLATE_END_ARGS()
		void Construct(const FArguments& A) { Deg = A._Degrees; OnChanged = A._OnChanged; }
		virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D(260, 260); }
		virtual bool SupportsKeyboardFocus() const override { return true; }
		virtual FReply OnKeyDown(const FGeometry&, const FKeyEvent& E) override
		{
			const FKey K = E.GetKey();
			const float D = Deg.Get(0.f);
			if (K == EKeys::Left || K == EKeys::Gamepad_DPad_Left || K == EKeys::Gamepad_LeftStick_Left) { OnChanged.ExecuteIfBound(FMath::Fmod(D + 355.f, 360.f)); return FReply::Handled(); }
			if (K == EKeys::Right || K == EKeys::Gamepad_DPad_Right || K == EKeys::Gamepad_LeftStick_Right) { OnChanged.ExecuteIfBound(FMath::Fmod(D + 5.f, 360.f)); return FReply::Handled(); }
			return FReply::Unhandled();
		}
		virtual FReply OnMouseButtonDown(const FGeometry& G, const FPointerEvent& E) override { bDrag = true; SetFrom(G, E); return FReply::Handled().CaptureMouse(SharedThis(this)).SetUserFocus(SharedThis(this), EFocusCause::Mouse); }
		virtual FReply OnMouseMove(const FGeometry& G, const FPointerEvent& E) override { if (bDrag) SetFrom(G, E); return bDrag ? FReply::Handled() : FReply::Unhandled(); }
		virtual FReply OnMouseButtonUp(const FGeometry&, const FPointerEvent&) override { bDrag = false; return FReply::Handled().ReleaseMouseCapture(); }
		virtual void OnMouseEnter(const FGeometry& G, const FPointerEvent& E) override { SLeafWidget::OnMouseEnter(G, E); if (SailUI::MouseIsActive()) FSlateApplication::Get().SetUserFocus(0, SharedThis(this), EFocusCause::Mouse); }
		virtual int32 OnPaint(const FPaintArgs&, const FGeometry& G, const FSlateRect&, FSlateWindowElementList& Out, int32 Layer, const FWidgetStyle& Style, bool) const override
		{
			const FVector2D S = G.GetLocalSize();
			const FVector2f C(S.X * 0.5f, S.Y * 0.5f);
			const float R = FMath::Min(S.X, S.Y) * 0.42f;
			auto Pt = [&](float Deg, float Rad) { const float A = FMath::DegreesToRadians(Deg); return C + FVector2f(FMath::Sin(A) * Rad, -FMath::Cos(A) * Rad); };
			TArray<FVector2f> Ring;
			for (int32 I = 0; I <= 72; ++I) Ring.Add(Pt(I * 5.f, R));
			FSlateDrawElement::MakeLines(Out, Layer, G.ToPaintGeometry(), Ring, ESlateDrawEffect::None, (HasKeyboardFocus() ? Accent : Line) * Style.GetColorAndOpacityTint(), true, HasKeyboardFocus() ? 3.f : 2.f);
			for (int32 I = 0; I < 36; ++I)
			{
				const float L = I % 9 == 0 ? 14.f : 7.f;
				FSlateDrawElement::MakeLines(Out, Layer, G.ToPaintGeometry(), { Pt(I * 10.f, R - L), Pt(I * 10.f, R) }, ESlateDrawEffect::None, Muted, true, 1.f);
			}
			const TCHAR* Card[] = { TEXT("N"), TEXT("E"), TEXT("S"), TEXT("W") };
			for (int32 I = 0; I < 4; ++I)
			{
				const FVector2f P = Pt(I * 90.f, R - 30.f) - FVector2f(7.f, 12.f);
				FSlateDrawElement::MakeText(Out, Layer + 1, G.ToPaintGeometry(FVector2f(30.f, 30.f), FSlateLayoutTransform(P)), FString(Card[I]), Font(EType::Label), ESlateDrawEffect::None, I == 0 ? Accent : Fg);
			}
			// The true wind arrow: on the rim at the direction it comes from, pointing at the centre.
			const float D = Deg.Get(0.f);
			const FVector2f Tail = Pt(D, R + 14.f), Head = Pt(D, R * 0.35f);
			FSlateDrawElement::MakeLines(Out, Layer + 2, G.ToPaintGeometry(), { Tail, Head }, ESlateDrawEffect::None, WindTrue, true, 4.f);
			const FVector2f Dir = (Head - Tail).GetSafeNormal(), Side(-Dir.Y, Dir.X);
			FSlateDrawElement::MakeLines(Out, Layer + 2, G.ToPaintGeometry(), { Head - Dir * 14.f + Side * 9.f, Head, Head - Dir * 14.f - Side * 9.f }, ESlateDrawEffect::None, WindTrue, true, 4.f);
			const FString Big = USailSessionSubsystem::CompassPoint(D), Small = FString::Printf(TEXT("%03.0f° TRUE"), D);
			FSlateDrawElement::MakeText(Out, Layer + 3, G.ToPaintGeometry(FVector2f(120.f, 40.f), FSlateLayoutTransform(C - FVector2f(Big.Len() * 9.f, 22.f))), Big, Font(EType::CardTitleM), ESlateDrawEffect::None, Fg);
			FSlateDrawElement::MakeText(Out, Layer + 3, G.ToPaintGeometry(FVector2f(120.f, 20.f), FSlateLayoutTransform(C + FVector2f(-30.f, 16.f))), Small, Font(EType::Label), ESlateDrawEffect::None, Muted);
			return Layer + 3;
		}
	private:
		void SetFrom(const FGeometry& G, const FPointerEvent& E)
		{
			const FVector2D L = G.AbsoluteToLocal(E.GetScreenSpacePosition()) - G.GetLocalSize() * 0.5;
			const float D = FMath::RadiansToDegrees(FMath::Atan2(float(L.X), float(-L.Y)));
			OnChanged.ExecuteIfBound(FMath::Fmod(FMath::RoundToFloat(D / 5.f) * 5.f + 360.f, 360.f));
		}
		TAttribute<float> Deg;
		TDelegate<void(float)> OnChanged;
		bool bDrag = false;
	};

	TSharedRef<SWidget> Fact(const FString& Value, const FString& Label)
	{
		return SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(Value, EType::Value, Fg) ]
			+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(Label, EType::Label, Muted) ];
	}

	TSharedRef<SWidget> SpecRow(const FString& Label, const FString& Value)
	{
		return SNew(SBorder).BorderImage(Rounded(FLinearColor::Transparent, 0.f)).Padding(FMargin(0.f, 6.f))
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().FillWidth(1.f)[ SailUI::Text(Label, EType::Ui, Muted) ]
			+ SHorizontalBox::Slot().AutoWidth()[ SailUI::Text(Value, EType::Value, Fg) ]
		];
	}
}

// ---------------------------------------------------------------- the stack

void SSailFrontEnd::Construct(const FArguments& A)
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	Player = A._Player;
	OnClose = A._OnClose;
	USailSessionSubsystem* Session = Player.IsValid() ? USailSessionSubsystem::Get(Player.Get()) : nullptr;
	const bool bInGame = A._Start == ESailScreen::Pause || A._Start == ESailScreen::Briefing || A._Start == ESailScreen::Quiz;
	// The menus' choices carry over when they close and open again before a cast off (the title's Logbook and back).
	Pending = Session && Session->bHasActive ? Session->Active : Session && Session->bHasPending && !bInGame ? Session->Pending : USailSessionSubsystem::MakeDefault();
	bMenusInGame = bInGame;
	RegisterInputTracker();
	// Showroom stills (docs/showroom-wiring/): the boat to show, the conditions to preview, and the menus drawn clear so
	// the stage shows (they still run).
	FParse::Value(SailingArgs::Dev(), TEXT("SailingShowroom="), ShowroomArg);
	FString PresetArg;
	if (FParse::Value(SailingArgs::Dev(), TEXT("SailingPreviewPreset="), PresetArg))
	{
		for (const FSailPreset& P : USailSessionSubsystem::Presets()) if (P.Id == FName(*PresetArg)) USailSessionSubsystem::ApplyPreset(Pending.Conditions, P);
	}
	if (FParse::Param(SailingArgs::Dev(), TEXT("SailingHideMenus"))) SetRenderOpacity(0.f);
	ChildSlot
	[
		SNew(SOverlay)
		+ SOverlay::Slot()[ SNew(SBackdrop).LeftAlpha(bInGame ? 0.80f : 0.86f).RightAlpha(bInGame ? 0.62f : 0.15f)
			.Visibility_Lambda([this]() { return IsGallery() && bGalleryClean ? EVisibility::Collapsed : EVisibility::HitTestInvisible; })
			.Showroom_Lambda([this]() { return IsStageScreen() || IsGallery(); })
			// (The Boat screen's left column ends at 460 px of 1440, Conditions' panel at 600, the gallery's list at 430.)
			.FadeEnd_Lambda([this]() { return Current() == ESailScreen::Boat ? 460.f / 1440.f : IsGallery() ? (bGalleryFull ? 0.f : 430.f / 1440.f) : 600.f / 1440.f; })
			// The swap's cover: the moment the new boat is built the screen is dark, and it clears over 150 ms.
			.Dip_Lambda([this]()
			{
				const ASailboatPawn* P = Current() == ESailScreen::Boat ? Pawn() : nullptr;
				const double Since = P && P->GetShowroomSwapTime() > 0.0 ? FPlatformTime::Seconds() - P->GetShowroomSwapTime() : 1e9;
				return Since < 0.15 ? float(0.6 * (1.0 - Since / 0.15)) : 0.f;
			}) ]
		+ SOverlay::Slot().Padding(FMargin(SafeX, SafeTop, SafeX, 0.f))[ SAssignNew(Body, SBox) ]
		+ SOverlay::Slot().VAlign(VAlign_Bottom)[ SAssignNew(Footer, SBox).Visibility_Lambda([this]() { return IsGallery() && bGalleryClean ? EVisibility::Collapsed : EVisibility::Visible; }) ]
	];
	Push(A._Start);
	RegisterActiveTimer(0.f, FWidgetActiveTimerDelegate::CreateSP(this, &SSailFrontEnd::TickShowroom));
}

SSailFrontEnd::~SSailFrontEnd()
{
	if (GalleryStage.IsValid()) CloseGallery(true);
	Showroom.End(Pawn(), GameMode());
	if (USailSessionSubsystem* Session = Player.IsValid() ? USailSessionSubsystem::Get(Player.Get()) : nullptr; Session && !bMenusInGame && !Session->bHasActive)
	{
		Session->Pending = Pending;
		Session->bHasPending = true;
	}
}

ASailingGameMode* SSailFrontEnd::GameMode() const
{
	UWorld* World = Player.IsValid() ? Player->GetWorld() : nullptr;
	return World ? World->GetAuthGameMode<ASailingGameMode>() : nullptr;
}

EActiveTimerReturnType SSailFrontEnd::TickShowroom(double Time, float)
{
	// The Boat screen shows the focused boat (focus is the selection there); every other screen the chosen one.
	const int32 Shown = Current() == ESailScreen::Boat ? (ShowroomArg >= 0 ? ShowroomArg : FocusedBoat) : Pending.Boat;
	// Inputs/ui-showroom/brief.md section 6: the Conditions screen's preview eases rather than pops. The wind and gusts
	// close on the choice over about 2 s (the waves and the heel build with them) and the clock sweeps at up to 3 hours a
	// second while the slider moves; while they move, the world is re-previewed five times a second. The direction, sky,
	// date and real day snap (the Mac's debounced preview, 200 ms after a change stands).
	const bool bConditions = Current() == ESailScreen::Conditions || Current() == ESailScreen::ConditionsInGame;
	const float Dt = BlendTickAt > 0.0 ? float(FMath::Clamp(Time - BlendTickAt, 0.0, 0.1)) : 0.f;
	BlendTickAt = Time;
	if (!bConditions) bBlendLive = false;
	else if (!bBlendLive) { Blend = Pending.Conditions; bBlendLive = true; BlendAppliedAt = Time; }
	else
	{
		const FSailConditions& To = Pending.Conditions;
		const float K = 1.f - FMath::Exp(-Dt / 0.67f);
		const float WindWas = Blend.WindKn, GustWas = Blend.GustKn, HourWas = Blend.LocalHour;
		Blend.WindKn = FMath::Abs(To.WindKn - Blend.WindKn) < 0.05f ? To.WindKn : Blend.WindKn + (To.WindKn - Blend.WindKn) * K;
		Blend.GustKn = FMath::Abs(To.GustKn - Blend.GustKn) < 0.05f ? To.GustKn : Blend.GustKn + (To.GustKn - Blend.GustKn) * K;
		Blend.LocalHour = Blend.LocalHour + FMath::Clamp(To.LocalHour - Blend.LocalHour, -3.f * Dt, 3.f * Dt);
		const float W = Blend.WindKn, G = Blend.GustKn, Hr = Blend.LocalHour;
		Blend = To;
		Blend.WindKn = W; Blend.GustKn = FMath::Max(G, W); Blend.LocalHour = Hr;
		const bool bMoving = Blend.WindKn != WindWas || Blend.GustKn != GustWas || Blend.LocalHour != HourWas;
		ASailingGameMode* GM = GameMode();
		if (bMoving && GM && Showroom.GetStage() == EShowroomStage::Weather && Time - BlendAppliedAt >= 0.2)
		{
			GM->PreviewConditions(Blend);
			BlendAppliedAt = Time;
		}
	}
	Showroom.Update(Pawn(), GameMode(), Current(), bMenusInGame, Shown, bConditions ? Blend : Pending.Conditions, Time);
	return EActiveTimerReturnType::Continue;
}

ASailboatPawn* SSailFrontEnd::Pawn() const
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	return Player.IsValid() ? Cast<ASailboatPawn>(Player->GetPawn()) : nullptr;
}

bool SSailFrontEnd::TravelsOnPush(ESailScreen From, ESailScreen To, bool bInGame, int32 PendingWorld, int32 LoadedWorld)
{
	return !bInGame && From == ESailScreen::World && To == ESailScreen::Launch && PendingWorld != LoadedWorld;
}

void SSailFrontEnd::Push(ESailScreen Screen)
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	if (bTravelling) return;
	const ASailingGameMode* GM = GameMode();
	if (GM && TravelsOnPush(Current(), Screen, bMenusInGame, Pending.World, GM->GetLoadedWorld()))
	{
		TravelToWorld(Screen);
		return;
	}
	Stack.Add(Build(Screen));
	Show(Stack.Last(), true);
}

void SSailFrontEnd::TravelToWorld(ESailScreen Resume)
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	bTravelling = true;
	const FString Name = SailCatalog::World(Pending.World).Name;
	UE_LOG(LogSailing, Display, TEXT("Menus: loading %s behind them (world %d)"), *Name, Pending.World);
	Body->SetContent(SNew(SBox).HAlign(HAlign_Center).VAlign(VAlign_Center)
		[ SailUI::Text(FString::Printf(TEXT("Loading %s"), *Name), EType::ScreenTitle, Fg) ]);
	Footer->SetContent(SNullWidget::NullWidget);
	RegisterActiveTimer(0.15f, FWidgetActiveTimerDelegate::CreateLambda([this, Resume](double, float)
	{
		if (USailSessionSubsystem* Session = Player.IsValid() ? USailSessionSubsystem::Get(Player.Get()) : nullptr)
		{
			Session->TravelBehindMenus(Pending, int32(Resume), Player.Get());
		}
		return EActiveTimerReturnType::Stop;
	}));
}

void SSailFrontEnd::Pop()
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	if (Stack.Num() <= 1)
	{
		// Pause's Back resumes; the title's asks to quit.
		if (Current() == ESailScreen::Pause || Current() == ESailScreen::Briefing || Current() == ESailScreen::Quiz) Close();
		else if (Current() == ESailScreen::Title) Confirm(TEXT("Quit Sailing Sim?"), TEXT("Quit"), [this]() { UKismetSystemLibrary::QuitGame(Player.Get(), Player.Get(), EQuitPreference::Quit, false); });
		return;
	}
	if (Current() == ESailScreen::Quiz) { Quiz.Reset(); CheckrideTierId.Reset(); }
	if (IsGallery() && GalleryStage.IsValid()) { GalleryBack(); return; }
	Stack.Pop();
	// Rebuild the uncovered screen: its summary rows may show choices made further on.
	const ESailScreen S = Stack.Last().Screen;
	Stack.Last() = Build(S);
	Show(Stack.Last(), false);
}

void SSailFrontEnd::Show(const FEntry& E, bool bForward)
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	Body->SetContent(E.Content.ToSharedRef());
	Footer->SetContent(E.Footer.IsValid() ? E.Footer.ToSharedRef() : SNullWidget::NullWidget);
	bTransitionForward = bForward;
	TransitionStart = FSlateApplication::Get().GetCurrentTime();
	if (!IsLow()) RegisterActiveTimer(0.f, FWidgetActiveTimerDelegate::CreateSP(this, &SSailFrontEnd::AnimateTransition));
	// Focus once the new screen has been laid out (a widget that has never been arranged has no path to focus).
	RegisterActiveTimer(0.f, FWidgetActiveTimerDelegate::CreateLambda([this](double, float) { FocusCurrent(); return EActiveTimerReturnType::Stop; }));
}

EActiveTimerReturnType SSailFrontEnd::AnimateTransition(double Time, float)
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	const float T = FMath::Clamp(float(Time - TransitionStart) / 0.18f, 0.f, 1.f);
	const float E = 1.f - FMath::Square(1.f - T);
	Body->SetRenderOpacity(E);
	Body->SetRenderTransform(FSlateRenderTransform(FVector2f((1.f - E) * 24.f * (bTransitionForward ? 1.f : -1.f), 0.f)));
	return T < 1.f ? EActiveTimerReturnType::Continue : EActiveTimerReturnType::Stop;
}

void SSailFrontEnd::FocusCurrent()
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	if (Stack.Num() && Stack.Last().Focus.IsValid()) FSlateApplication::Get().SetUserFocus(0, Stack.Last().Focus, EFocusCause::SetDirectly);
	else FSlateApplication::Get().SetUserFocus(0, SharedThis(this), EFocusCause::SetDirectly);
}

FReply SSailFrontEnd::OnPreviewKeyDown(const FGeometry&, const FKeyEvent& E)
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	if (ListeningRow < 0 || Current() != ESailScreen::Controls) return FReply::Unhandled();
	// Rebinding: the next key goes to the row's column; Esc or B cancels. The keyboard column takes keyboard keys (a
	// gamepad key cancels), the gamepad column buttons and the D-pad (sticks and triggers stay on their axes).
	const FKey K = E.GetKey();
	bool bDone = true;
	if (K == EKeys::Escape || K == EKeys::Gamepad_FaceButton_Right || K.IsMouseButton()) ControlsMessage = TEXT("Cancelled");
	else if (bListeningPad && !SailingBindings::IsPadButton(K))
	{
		bDone = false;
		ControlsMessage = SailingBindings::IsPadAxis(K) ? FString(TEXT("Sticks and triggers stay on their axes: press a button or the D-pad (B cancels)"))
			: FString(TEXT("Press a controller button or the D-pad (Esc or B cancels)"));
	}
	else if (!bListeningPad && !SailingBindings::IsKeyboardKey(K)) ControlsMessage = TEXT("Cancelled");
	else if (ASailboatPawn* P = Pawn())
	{
		P->UIAssignKey(ListeningRow, K);
		ControlsMessage = P->GetKeysMessage();
	}
	if (bDone) ListeningRow = -1;
	Stack.Last() = Build(ESailScreen::Controls);
	Show(Stack.Last(), true);
	return FReply::Handled();
}

void SSailFrontEnd::ListenControls(int32 Row, bool bPad)
{
	ListeningRow = Row;
	bListeningPad = bPad;
	ControlsMessage = bPad ? TEXT("Press a controller button or the D-pad… (B cancels)") : TEXT("Press a key… (Esc cancels)");
	Stack.Last() = Build(ESailScreen::Controls);
	Show(Stack.Last(), true);
}

FReply SSailFrontEnd::OnKeyDown(const FGeometry&, const FKeyEvent& E)
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	const FKey K = E.GetKey();
	if (IsGallery())
	{
		const FReply R = GalleryKeyDown(E);
		if (R.IsEventHandled()) return R;
	}
	// Controls: Tab or Y rebinds the focused row's gamepad button (Enter or A, the row's click, its keyboard key).
	if (Current() == ESailScreen::Controls && ListeningRow < 0 && (K == EKeys::Tab || K == EKeys::Gamepad_FaceButton_Top))
	{
		const ASailboatPawn* P = Pawn();
		if (P && FocusedControlRow < P->GetKeyRows().Num()) ListenControls(FocusedControlRow, true);
		return FReply::Handled();
	}
	if (IsStageScreen())
	{
		// Inputs/ui-showroom/brief.md sections 2 and 6: V or the controller's View button hides the panels; it, Esc or B
		// bring them back. On the Boat screen LB/RB and Q/E move along the strip (Left and Right do too, between its
		// cards). Home or R3 puts the camera back on its framing.
		if (K == EKeys::V || K == EKeys::Gamepad_Special_Left || (bViewMode && IsBackKey(K))) { bViewMode = !bViewMode; return FReply::Handled(); }
		if (Current() == ESailScreen::Boat && (K == EKeys::Q || K == EKeys::Gamepad_LeftShoulder)) { StepBoat(-1); return FReply::Handled(); }
		if (Current() == ESailScreen::Boat && (K == EKeys::E || K == EKeys::Gamepad_RightShoulder)) { StepBoat(1); return FReply::Handled(); }
		if (K == EKeys::Home || K == EKeys::Gamepad_RightThumbstick) { if (ASailboatPawn* P = Pawn()) P->ShowroomResetView(); return FReply::Handled(); }
	}
	if (IsBackKey(K)) { Pop(); return FReply::Handled(); }
	if (const TSharedPtr<SScrollBox> Scroll = ActiveScroll())
	{
		// Credits and the world cards' descriptions (Bean's UI feedback, Oct 27: the cards cut their text off): arrows, the
		// D-pad and the stick's flicks step a few lines, Page Up/Down a screen (and on Credits the shoulders and Space too;
		// the world cards take Left and Right to move between cards, so only Up and Down scroll there).
		const bool bCredits = Current() == ESailScreen::Credits;
		const float Step = bCredits ? 60.f : 24.f, Page = FMath::Max(bCredits ? 200.f : 40.f, float(Scroll->GetCachedGeometry().GetLocalSize().Y) - (bCredits ? 80.f : 16.f));
		float To = Scroll->GetScrollOffset();
		if (K == EKeys::Down || K == EKeys::S || K == EKeys::Gamepad_DPad_Down || K == EKeys::Gamepad_LeftStick_Down) To += Step;
		else if (K == EKeys::Up || K == EKeys::W || K == EKeys::Gamepad_DPad_Up || K == EKeys::Gamepad_LeftStick_Up) To -= Step;
		else if (K == EKeys::PageDown || (bCredits && (K == EKeys::SpaceBar || K == EKeys::Gamepad_RightShoulder || K == EKeys::Gamepad_RightTrigger))) To += Page;
		else if (K == EKeys::PageUp || (bCredits && (K == EKeys::Gamepad_LeftShoulder || K == EKeys::Gamepad_LeftTrigger))) To -= Page;
		else if (K == EKeys::Home) To = 0.f;
		else if (K == EKeys::End) { Scroll->ScrollToEnd(); return FReply::Handled(); }
		else return FReply::Unhandled();
		Scroll->SetScrollOffset(FMath::Clamp(To, 0.f, Scroll->GetScrollOffsetOfEnd()));
		return FReply::Handled();
	}
	if (Current() == ESailScreen::Settings && (K == EKeys::Q || K == EKeys::E || K == EKeys::Gamepad_LeftShoulder || K == EKeys::Gamepad_RightShoulder))
	{
		SetSettingsTab(SettingsTab + ((K == EKeys::Q || K == EKeys::Gamepad_LeftShoulder) ? 4 : 1));
		return FReply::Handled();
	}
	if (Current() == ESailScreen::Mode && (K == EKeys::Gamepad_Special_Right))
	{
		CastOff();
		return FReply::Handled();
	}
	return FReply::Unhandled();
}

FReply SSailFrontEnd::OnAnalogValueChanged(const FGeometry&, const FAnalogInputEvent& E)
{
	if (IsGallery() && bGalleryViewer && (E.GetKey() == EKeys::Gamepad_LeftX || E.GetKey() == EKeys::Gamepad_LeftY))
	{
		const float V = FMath::Abs(E.GetAnalogValue()) > 0.15f ? E.GetAnalogValue() : 0.f;
		const bool bWasIdle = OrbitStick.IsZero() && OrbitZoomStick == 0.f && GalleryPanStick.IsZero();
		(E.GetKey() == EKeys::Gamepad_LeftX ? GalleryPanStick.X : GalleryPanStick.Y) = V;
		if (bWasIdle && !GalleryPanStick.IsZero()) RegisterActiveTimer(0.f, FWidgetActiveTimerDelegate::CreateSP(this, &SSailFrontEnd::TickOrbitStick));
		return FReply::Handled();
	}
	if (IsStageScreen() || IsGallery())
	{
		// The right stick turns the showroom's camera, the triggers zoom it (LT out, RT in); held, applied each frame.
		const FKey K = E.GetKey();
		const float V = FMath::Abs(E.GetAnalogValue()) > 0.15f ? E.GetAnalogValue() : 0.f;
		const bool bWasIdle = OrbitStick.IsZero() && OrbitZoomStick == 0.f && GalleryPanStick.IsZero();
		if (K == EKeys::Gamepad_RightX) OrbitStick.X = V;
		else if (K == EKeys::Gamepad_RightY) OrbitStick.Y = V;
		else if (K == EKeys::Gamepad_RightTriggerAxis) OrbitZoomStick = V;
		else if (K == EKeys::Gamepad_LeftTriggerAxis) OrbitZoomStick = -V;
		else return FReply::Unhandled();
		if (bWasIdle && !(OrbitStick.IsZero() && OrbitZoomStick == 0.f)) RegisterActiveTimer(0.f, FWidgetActiveTimerDelegate::CreateSP(this, &SSailFrontEnd::TickOrbitStick));
		return FReply::Handled();
	}
	if (!ActiveScroll().IsValid()) return FReply::Unhandled();
	// Credits: either stick scrolls (up is positive Y); the world cards: the right stick (the left one moves between cards).
	// The timer runs while it is held.
	const FKey K = E.GetKey();
	if (K != EKeys::Gamepad_RightY && (K != EKeys::Gamepad_LeftY || Current() != ESailScreen::Credits)) return FReply::Unhandled();
	const float V = FMath::Abs(E.GetAnalogValue()) > 0.2f ? -E.GetAnalogValue() : 0.f;
	if (V != 0.f && ScrollStick == 0.f) RegisterActiveTimer(0.f, FWidgetActiveTimerDelegate::CreateSP(this, &SSailFrontEnd::ScrollActive));
	ScrollStick = V;
	return FReply::Handled();
}

TSharedPtr<SScrollBox> SSailFrontEnd::ActiveScroll() const
{
	if (Current() == ESailScreen::Credits) return CreditsScroll;
	if (Current() != ESailScreen::World) return nullptr;
	for (int32 I = 0; I < WorldCards.Num() && I < WorldScrolls.Num(); ++I)
	{
		if (WorldCards[I].IsValid() && WorldCards[I]->HasKeyboardFocus()) return WorldScrolls[I];
	}
	return nullptr;
}

EActiveTimerReturnType SSailFrontEnd::ScrollActive(double, float Delta)
{
	const TSharedPtr<SScrollBox> Scroll = ActiveScroll();
	if (!Scroll.IsValid() || ScrollStick == 0.f) { ScrollStick = 0.f; return EActiveTimerReturnType::Stop; }
	const float Speed = Current() == ESailScreen::Credits ? 900.f : 260.f;
	Scroll->SetScrollOffset(FMath::Clamp(Scroll->GetScrollOffset() + ScrollStick * Speed * Delta, 0.f, Scroll->GetScrollOffsetOfEnd()));
	return EActiveTimerReturnType::Continue;
}

EActiveTimerReturnType SSailFrontEnd::TickOrbitStick(double, float Delta)
{
	ASailboatPawn* P = Pawn();
	if (IsGallery() && GalleryStage.IsValid() && !(OrbitStick.IsZero() && OrbitZoomStick == 0.f && GalleryPanStick.IsZero()))
	{
		// The gallery: the same rates on its stage; the left stick pans (the viewer focused), half the asset a second.
		AGalleryStage* G = GalleryStage.Get();
		if (!OrbitStick.IsZero()) { G->Orbit(OrbitStick * 90.0 * Delta); bGalleryCompareShown = false; }
		OrbitZoomCarry += OrbitZoomStick * Delta / 0.15f;
		const int32 Steps = FMath::TruncToInt32(OrbitZoomCarry);
		if (Steps != 0) { G->Zoom(float(Steps)); OrbitZoomCarry -= float(Steps); }
		if (!GalleryPanStick.IsZero()) G->Pan(GalleryPanStick * G->GetStats().SizeM.Size() * 50.0 * Delta);
		return EActiveTimerReturnType::Continue;
	}
	if (!IsStageScreen() || !P || (OrbitStick.IsZero() && OrbitZoomStick == 0.f))
	{
		OrbitStick = FVector2D::ZeroVector; OrbitZoomStick = 0.f; OrbitZoomCarry = 0.f; GalleryPanStick = FVector2D::ZeroVector;
		return EActiveTimerReturnType::Stop;
	}
	// 90 deg/s at full stick; the zoom a notch every 0.15 s at full trigger.
	P->ShowroomLook(OrbitStick * 90.0 * Delta);
	OrbitZoomCarry += OrbitZoomStick * Delta / 0.15f;
	const int32 Notches = FMath::TruncToInt32(OrbitZoomCarry);
	if (Notches != 0) { P->ShowroomZoom(Notches); OrbitZoomCarry -= float(Notches); }
	return EActiveTimerReturnType::Continue;
}

bool SSailFrontEnd::IsStageScreen() const
{
	const ESailScreen S = Current();
	return S == ESailScreen::Boat || S == ESailScreen::Conditions || S == ESailScreen::ConditionsInGame;
}

void SSailFrontEnd::StepBoat(int32 Dir)
{
	const int32 N = BoatCardTypes.Num();
	if (N == 0) return;
	const int32 At = FMath::Max(BoatCardTypes.IndexOfByKey(FocusedBoat), 0);
	const int32 To = (At + Dir % N + N) % N;
	FocusedBoat = BoatCardTypes[To];
	if (BoatCards.IsValidIndex(To) && BoatCards[To].IsValid()) FSlateApplication::Get().SetUserFocus(0, BoatCards[To], EFocusCause::Navigation);
}

FReply SSailFrontEnd::OnMouseButtonDown(const FGeometry&, const FPointerEvent& E)
{
	// (Buttons and cards take their own clicks; what reaches here is empty space.)
	if (IsGallery() && GalleryStage.IsValid() && (E.GetEffectingButton() == EKeys::LeftMouseButton || E.GetEffectingButton() == EKeys::RightMouseButton))
	{
		bGalleryPanDrag = E.GetEffectingButton() == EKeys::RightMouseButton || E.IsShiftDown();
		bOrbitDrag = true;
		bGalleryCompareShown = false;
		return FReply::Handled().CaptureMouse(SharedThis(this));
	}
	if (!IsStageScreen() || E.GetEffectingButton() != EKeys::LeftMouseButton) return FReply::Unhandled();
	bOrbitDrag = true;
	return FReply::Handled().CaptureMouse(SharedThis(this));
}

FReply SSailFrontEnd::OnMouseButtonUp(const FGeometry&, const FPointerEvent& E)
{
	if (!bOrbitDrag || (E.GetEffectingButton() != EKeys::LeftMouseButton && !(IsGallery() && E.GetEffectingButton() == EKeys::RightMouseButton))) return FReply::Unhandled();
	bOrbitDrag = false;
	return FReply::Handled().ReleaseMouseCapture();
}

FReply SSailFrontEnd::OnMouseMove(const FGeometry&, const FPointerEvent& E)
{
	if (!bOrbitDrag || !HasMouseCapture()) return FReply::Unhandled();
	if (IsGallery())
	{
		if (AGalleryStage* G = GalleryStage.Get())
		{
			// A pan of the cursor's move at the asset's scale (its size over the screen's height); an orbit 0.25 deg a pixel.
			if (bGalleryPanDrag) G->Pan(FVector2D(-E.GetCursorDelta().X, E.GetCursorDelta().Y) * G->GetStats().SizeM.Size() * 100.0 / 900.0);
			else G->Orbit(FVector2D(E.GetCursorDelta().X * 0.25, -E.GetCursorDelta().Y * 0.25));
		}
		return FReply::Handled();
	}
	if (ASailboatPawn* P = Pawn()) P->ShowroomLook(FVector2D(E.GetCursorDelta().X * 0.25, -E.GetCursorDelta().Y * 0.25));
	return FReply::Handled();
}

FReply SSailFrontEnd::OnMouseWheel(const FGeometry&, const FPointerEvent& E)
{
	if (IsGallery())
	{
		if (AGalleryStage* G = GalleryStage.Get()) G->Zoom(E.GetWheelDelta() > 0.f ? 1.f : -1.f);
		return FReply::Handled();
	}
	if (!IsStageScreen()) return FReply::Unhandled();
	if (ASailboatPawn* P = Pawn()) P->ShowroomZoom(E.GetWheelDelta() > 0.f ? 1 : -1);
	return FReply::Handled();
}

void SSailFrontEnd::SetSettingsTab(int32 Tab)
{
	SettingsTab = (Tab % 5 + 5) % 5;
	Stack.Last() = Build(ESailScreen::Settings);
	Show(Stack.Last(), true);
}

void SSailFrontEnd::CastOff()
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	if (USailSessionSubsystem* Session = Player.IsValid() ? USailSessionSubsystem::Get(Player.Get()) : nullptr)
	{
		Session->StartSession(Pending, Player.Get());
	}
}

void SSailFrontEnd::Close()
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	OnClose.ExecuteIfBound();
}

void SSailFrontEnd::Confirm(const FString& Question, const FString& Yes, TFunction<void()> OnYes)
{
	Confirm(Question, Yes, MoveTemp(OnYes), FString(), nullptr);
}

void SSailFrontEnd::Confirm(const FString& Question, const FString& Yes, TFunction<void()> OnYes, const FString& No, TFunction<void()> OnNo)
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	ConfirmQuestion = Question;
	ConfirmYes = Yes;
	ConfirmAction = MoveTemp(OnYes);
	ConfirmNo = No;
	ConfirmNoAction = MoveTemp(OnNo);
	Push(ESailScreen::Confirm);
}

SSailFrontEnd::FEntry SSailFrontEnd::Build(ESailScreen S)
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	FEntry E;
	switch (S)
	{
	case ESailScreen::Title: E = BuildTitle(); break;
	case ESailScreen::World: E = BuildWorld(); break;
	case ESailScreen::Launch: E = BuildLaunch(); break;
	case ESailScreen::Boat: E = BuildBoat(); break;
	case ESailScreen::Conditions: E = BuildConditions(false); break;
	case ESailScreen::ConditionsInGame: E = BuildConditions(true); break;
	case ESailScreen::Mode: E = BuildMode(); break;
	case ESailScreen::Pause: E = BuildPause(); break;
	case ESailScreen::Settings: E = BuildSettings(); break;
	case ESailScreen::Controls: E = BuildControls(); break;
	case ESailScreen::Confirm: E = BuildConfirm(); break;
	case ESailScreen::Briefing: E = BuildBriefing(); break;
	case ESailScreen::Quiz: if (Quiz.Num() == 0) StartQuiz(); E = BuildQuiz(); break;
	case ESailScreen::Credits: E = BuildCredits(); break;
	case ESailScreen::Career: E = BuildCareer(); break;
	case ESailScreen::Gallery: E = BuildGallery(); break;
	}
	E.Screen = S;
	return E;
}

// ---------------------------------------------------------------- 5.1 Title

SSailFrontEnd::FEntry SSailFrontEnd::BuildTitle()
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	FEntry E;
	const USailSessionSave* Save = USailSessionSave::Get();
	TSharedRef<SVerticalBox> Menu = SNew(SVerticalBox);
	TSharedPtr<SWidget> First;
	auto Item = [&](const FString& Label, const FString& Sub, FSimpleDelegate Do)
	{
		// Career 1 made it nine items: a little tighter, so Quit stays clear of the prompt bar at 1080 lines (tighter still
		// with the developers' tenth, Gallery).
		const bool bTen = USailingSettings::DeveloperTools();
		TSharedRef<SSailButton> B = SNew(SSailButton).Look(EButtonLook::MenuItem).OnClicked(Do).Padding(FMargin(18.f, bTen ? 1.f : 3.f))
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().FillWidth(1.f).VAlign(VAlign_Center)[ SailUI::Text(Label, EType::MenuItem, Fg) ]
			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)[ SailUI::Text(Sub, EType::Small, Muted) ]
		];
		Menu->AddSlot().AutoHeight().Padding(0.f, bTen ? 0.f : 1.f)[ SNew(SBox).WidthOverride(560.f)[ B ] ];
		if (!First.IsValid()) First = B;
	};
	const SailCatalog::FWorld& LastWorld = SailCatalog::World(Save->Last.World);
	if (Save->bHasLast)
	{
		const FString Spot = LastWorld.Spots.IsValidIndex(Save->Last.LaunchSpot) ? LastWorld.Spots[Save->Last.LaunchSpot].Name : FString();
		Item(TEXT("Continue"), SailCatalog::Boat(Save->Last.Boat).Name + TEXT(" · ") + Spot,
			FSimpleDelegate::CreateLambda([this, Save]() { Pending = Save->Last; CastOff(); }));
	}
	Item(TEXT("Sail"), TEXT("Pick world, boat and weather"), FSimpleDelegate::CreateLambda([this]() { Pending = USailSessionSubsystem::MakeDefault(); Push(ESailScreen::World); }));
	{
		// Career 1: the first open tier without its certificate, and how far along it is.
		const FCareerProgress Career = SailCareer::Progress();
		FString Sub = TEXT("Lessons, checkrides, certificates");
		for (const FCareerTier& T : FCareerContent::Get().Tiers)
		{
			if (!Career.IsTierOpen(T.Id) || !T.IsReady()) continue;
			Sub = Career.HasCertificate(T.CertificateId) ? T.CertificateName
				: FString::Printf(TEXT("%s · %d of %d lessons"), *T.Name, Career.LessonsAtLeast(T, ECareerMedal::Bronze), T.Lessons.Num());
			if (!Career.HasCertificate(T.CertificateId)) break;
		}
		if (SailCareer::IsFreeSail()) Sub = TEXT("Medals count in Career mode");
		Item(TEXT("Career"), Sub, FSimpleDelegate::CreateLambda([this]() { Push(ESailScreen::Career); }));
	}
	const int32 Passed = Save->DrillsPassed.Num();
	Item(TEXT("ASA 101 drills"), FString::Printf(TEXT("6 drills · %d passed"), Passed), FSimpleDelegate::CreateLambda([this, Save]()
	{
		Pending = USailSessionSubsystem::MakeDefault();
		Pending.Mode = ESailMode::Drill;
		for (int32 I = 0; I < 6; ++I) if (!Save->DrillsPassed.Contains(I)) { Pending.DrillIndex = I; break; }
		Push(ESailScreen::World);
	}));
	Item(TEXT("Race"), TEXT("vs five AI boats"), FSimpleDelegate::CreateLambda([this]() { Pending = USailSessionSubsystem::MakeDefault(); Pending.Mode = ESailMode::Race; Push(ESailScreen::World); }));
	Item(TEXT("Logbook"), TEXT("This session's log"), FSimpleDelegate::CreateLambda([this]() { if (ASailboatPawn* P = Pawn()) P->SetLogOpen(true); Close(); }));
	Item(TEXT("Replays"), TEXT("Watch your last run"), FSimpleDelegate::CreateLambda([this]() { if (ASailboatPawn* P = Pawn()) P->WatchLastRun(); Close(); }));
	Item(TEXT("Settings"), FString(), FSimpleDelegate::CreateLambda([this]() { Push(ESailScreen::Settings); }));
	// Inputs/gallery/brief.md section 6: developer tools (USailingSettings::bShowDeveloperTools: on while Bean playtests, an ini line turns it off).
	if (USailingSettings::DeveloperTools()) Item(TEXT("Gallery"), TEXT("Developer · every asset"), FSimpleDelegate::CreateLambda([this]() { Push(ESailScreen::Gallery); }));
	Item(TEXT("Credits"), FString(), FSimpleDelegate::CreateLambda([this]() { Push(ESailScreen::Credits); }));
	Item(TEXT("Quit"), FString(), FSimpleDelegate::CreateLambda([this]() { Pop(); }));

	TSharedRef<SWidget> Card = SNullWidget::NullWidget;
	if (Save->bHasLast)
	{
		const FSailSessionConfig& L = Save->Last;
		const FSailConditions& C = L.Conditions;
		const FString Spot = LastWorld.Spots.IsValidIndex(L.LaunchSpot) ? LastWorld.Spots[L.LaunchSpot].Name : FString();
		FString Detail = FString::Printf(TEXT("%s · %.0f kn %s gusting %.0f · %s · %s mode, %s."), *Spot, C.WindKn, *USailSessionSubsystem::CompassPoint(C.WindFromDeg),
			C.GustKn, *USailSessionSubsystem::SkyName(C.Sky), L.bLearningMode ? TEXT("Learning") : TEXT("Game"), L.bEasy ? TEXT("easy") : TEXT("realistic"));
		if (L.Mode == ESailMode::Drill) Detail += FString::Printf(TEXT(" Drill %d, %s, was in progress."), L.DrillIndex + 1, DrillName(ESailingDrill(L.DrillIndex + 1)));
		Card = SNew(SBox).WidthOverride(460.f)
		[
			PanelBox(SNew(SVerticalBox)
				+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(FString::Printf(TEXT("Last session · %s · %s"), *ShortDate(L.SavedAt), L.bFreeSail ? TEXT("Free Sail") : TEXT("Career")), EType::Eyebrow, Accent) ]
				+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 6.f)[ SailUI::Text(SailCatalog::Boat(L.Boat).Name + TEXT(" on ") + LastWorld.Name, EType::CardTitleS, Fg) ]
				+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(Detail, EType::Small, Muted, true) ])
		];
	}
	// Free Sail: the play mode (docs/free-sail). Career opens places and boats with certificates and grades the lessons;
	// Free Sail opens everything and earns no medals. The menus below follow it; Continue keeps its own session's mode.
	TSharedRef<SSailChoice> ModeChoice = SNew(SSailChoice).Label(TEXT("Mode")).Options({ TEXT("Career"), TEXT("Free Sail") })
		.Index_Lambda([]() { return SailCareer::IsFreeSail() ? 1 : 0; })
		.OnChanged_Lambda([this](int32 I)
		{
			USailingSettings* S = USailingSettings::Get();
			if (S->bFreeSail == (I == 1)) return;
			S->bFreeSail = I == 1;
			S->Save();
			bTitleFocusMode = true;   // rebuilt for the Career line; keep the switch focused
			Stack.Last() = Build(ESailScreen::Title);
			Show(Stack.Last(), true);
		});
	const FString ModeLine = SailCareer::IsFreeSail()
		? TEXT("Every world, boat, condition and mode open. No medals; the logbook still counts.")
		: TEXT("Earn certificates to open places and boats. Lessons are graded.");
	E.Content = SNew(SOverlay)
		+ SOverlay::Slot().HAlign(HAlign_Left).VAlign(VAlign_Center)
		[
			SNew(SVerticalBox)
			// The mode switch sits beside the logo's short second line, so the menu keeps its height.
			+ SVerticalBox::Slot().AutoHeight()
			[
				SNew(SBox).WidthOverride(560.f)
				[
					SNew(SOverlay)
					+ SOverlay::Slot()[ SNew(STextBlock).Text(FText::FromString(TEXT("SAILING\nSIM"))).Font(Font(EType::Logo)).ColorAndOpacity(Fg).LineHeightPercentage(0.78f) ]
					+ SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Bottom).Padding(0.f, 0.f, 0.f, 6.f)
					[
						SNew(SBox).WidthOverride(330.f)
						[
							PanelBox(SNew(SVerticalBox)
								+ SVerticalBox::Slot().AutoHeight()[ ModeChoice ]
								+ SVerticalBox::Slot().AutoHeight().Padding(16.f, 0.f, 16.f, 10.f)[ SailUI::Text(ModeLine, EType::Small, Muted, true) ],
								FMargin(0.f))
						]
					]
				]
			]
			+ SVerticalBox::Slot().AutoHeight().Padding(4.f, 6.f, 0.f, 36.f)[ SNew(STextBlock).Text(FText::FromString(TEXT("LAKE RAY HUBBARD  ·  GALVESTON BAY")))
				.Font([] { FSlateFontInfo F = Font(EType::Eyebrow); F.LetterSpacing = 320; return F; }()).ColorAndOpacity(Muted) ]
			+ SVerticalBox::Slot().AutoHeight()[ Menu ]
		]
		+ SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Top)[ SailUI::Text(TEXT("Graphics G4 build"), EType::Label, Dim) ]
		+ SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Bottom).Padding(0.f, 0.f, 0.f, 90.f)[ Card ];
	E.Focus = bTitleFocusMode ? TSharedPtr<SWidget>(ModeChoice) : First;
	bTitleFocusMode = false;
	// Slice #406: a tester build names itself in the corner (its commit and date), so a report says which build it was.
	const FString Stamp = SailCatalog::BuildStamp();
	const FString Hint = FString(TEXT("Left / Right on Mode: Career or Free Sail")) + (Stamp.IsEmpty() ? FString() : TEXT("     Build ") + Stamp);
	E.Footer = PromptBar({ Prompt(TEXT("Enter"), TEXT("A"), TEXT("Select")), Prompt(TEXT("Esc"), TEXT("B"), TEXT("Quit")) }, Hint);
	return E;
}

// ---------------------------------------------------------------- 5.2 World

SSailFrontEnd::FEntry SSailFrontEnd::BuildWorld()
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	FEntry E;
	TSharedRef<SHorizontalBox> Cards = SNew(SHorizontalBox);
	WorldScrolls.Reset();
	WorldCards.Reset();
	// Career 1: worlds open as certificates are earned (all of them in Free Sail).
	const FCareerProgress Career = SailCareer::Progress();
	if (!Career.IsWorldOpen(FSailSave::WorldId(Pending.World == 2 ? 1 : Pending.World))) { Pending.World = 0; Pending.LaunchSpot = 0; }
	for (const SailCatalog::FWorld& W : SailCatalog::Worlds())
	{
		const FString Locked = Career.WorldLockReason(W.Id);
		TSharedPtr<FSlateBrush> Art = TextureBrush(W.CardTexture);
		TSharedRef<SHorizontalBox> Facts = SNew(SHorizontalBox);
		for (const TPair<FString, FString>& F : W.Facts) Facts->AddSlot().FillWidth(1.f)[ Fact(F.Key, F.Value) ];
		const int32 Index = W.Index;
		// Bean's UI feedback (Oct 27): the description scrolls in its 80 px (the wheel over the card, Up and Down, the D-pad,
		// Page Up and Down, the right stick), with a thin bar that shows only when there is more.
		TSharedRef<SScrollBox> Scroll = SNew(SScrollBox).ScrollBarThickness(FVector2D(3.f, 3.f)).ScrollBarPadding(FMargin(4.f, 0.f, 0.f, 0.f))
			+ SScrollBox::Slot().Padding(0.f, 0.f, 8.f, 0.f)[ SailUI::Text(Locked.IsEmpty() ? W.Description : Locked, EType::Body, Locked.IsEmpty() ? Muted : Fg, true) ];
		TSharedRef<SSailButton> Card = SNew(SSailButton).Padding(FMargin(0.f)).IsEnabled(Locked.IsEmpty()).IsSelected_Lambda([this, Index]() { return Pending.World == Index; })
			.OnClicked_Lambda([this, Index]() { if (Pending.World != Index) { Pending.World = Index; Pending.LaunchSpot = 0; if (Index == 0 && Pending.Mode == ESailMode::Passage) Pending.Mode = ESailMode::Free; } Push(ESailScreen::Launch); })
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()
			[
				SNew(SOverlay)
				+ SOverlay::Slot()[ SNew(SBox).HeightOverride(300.f)[ SNew(SImage).Image_Lambda([Art]() { return Art.Get(); }) ] ]
				+ SOverlay::Slot().HAlign(HAlign_Left).VAlign(VAlign_Top).Padding(16.f)[ Pill(Locked.IsEmpty() ? W.Tagline : FString(TEXT("Locked")), W.Index == 0) ]
			]
			+ SVerticalBox::Slot().AutoHeight().Padding(24.f, 20.f, 24.f, 6.f)[ SailUI::Text(W.Name, EType::CardTitle, Fg) ]
			+ SVerticalBox::Slot().AutoHeight().Padding(24.f, 0.f, 24.f, 0.f)[ SNew(SBox).HeightOverride(80.f)[ Scroll ] ]
			// "Read more" while the text runs on below the box.
			+ SVerticalBox::Slot().AutoHeight().Padding(24.f, 2.f, 24.f, 12.f)
			[
				SNew(SBox).HeightOverride(18.f).Visibility_Lambda([Scroll]()
					{ return Scroll->GetScrollOffsetOfEnd() - Scroll->GetScrollOffset() > 1.f ? EVisibility::HitTestInvisible : EVisibility::Hidden; })
				[ SailUI::Text(TEXT("Read more  \u2193"), EType::Label, Accent) ]
			]
			+ SVerticalBox::Slot().AutoHeight().Padding(24.f, 0.f, 24.f, 22.f)[ Facts ]
		];
		WorldScrolls.Add(Scroll);
		WorldCards.Add(Card);
		Cards->AddSlot().FillWidth(1.f).Padding(W.Index == 0 ? FMargin(0.f, 0.f, 16.f, 0.f) : FMargin(16.f, 0.f, 0.f, 0.f))[ Card ];
		if (W.Index == FMath::Min(Pending.World, 1)) E.Focus = Card;
	}
	E.Content = SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight()[ Header(TEXT("New session"), TEXT("Choose a world"), 1) ]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 28.f, 0.f, 0.f)[ Cards ];
	E.Footer = PromptBar({ Prompt(TEXT("Enter"), TEXT("A"), TEXT("Choose")), Prompt(TEXT("\u2191 \u2193"), TEXT("R \u2195"), TEXT("Read more")),
		Prompt(TEXT("Esc"), TEXT("B"), TEXT("Back")) }, TEXT("Worlds load from the same map: switching reloads it"));
	return E;
}

// ---------------------------------------------------------------- 5.3 Launch spot

SSailFrontEnd::FEntry SSailFrontEnd::BuildLaunch()
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	FEntry E;
	const SailCatalog::FWorld& W = SailCatalog::World(Pending.World);
	TSharedPtr<FSlateBrush> Map = TextureBrush(W.MapTexture);
	const FVector2D MapSize = Map->ImageSize.X > 0 ? FVector2D(Map->ImageSize) : FVector2D(1000, 1000);
	TSharedRef<SConstraintCanvas> Pins = SNew(SConstraintCanvas);
	TSharedRef<SVerticalBox> List = SNew(SVerticalBox);
	TArray<TSharedPtr<SWidget>> Rows;
	for (int32 I = 0; I < W.Spots.Num(); ++I)
	{
		const SailCatalog::FSpot& S = W.Spots[I];
		// The spot on the map: the map covers the world's grid, north up.
		const float U = float((S.East - W.GridEast) / W.GridWidthM), V = float(1.0 - (S.North - W.GridNorth) / W.GridHeightM);
		const float Pin = MapSize.Y * 0.045f;
		auto Select = [this, I]() { if (Pending.LaunchSpot == I) Push(ESailScreen::Boat); else Pending.LaunchSpot = I; };
		Pins->AddSlot().Anchors(FAnchors(U, V)).Offset(FMargin(0.f, 0.f, Pin, Pin)).Alignment(FVector2D(0.5f, 0.5f)).AutoSize(false)
		[
			SNew(SSailButton).Look(EButtonLook::Pin).Padding(FMargin(0.f)).IsSelected_Lambda([this, I]() { return Pending.LaunchSpot == I; }).OnClicked_Lambda(Select)
			[
				SNew(SBox).HAlign(HAlign_Center).VAlign(VAlign_Center)
				[
					SNew(STextBlock).Text(FText::AsNumber(I + 1)).Font([&] { FSlateFontInfo F = Font(EType::CardTitleS); F.Size = Pin * 0.42f; return F; }())
					.ColorAndOpacity_Lambda([this, I]() { return FSlateColor(Pending.LaunchSpot == I ? AccentInk : Fg); })
				]
			]
		];
		TSharedRef<SSailButton> Row = SNew(SSailButton).Padding(FMargin(16.f, 12.f)).IsSelected_Lambda([this, I]() { return Pending.LaunchSpot == I; }).OnClicked_Lambda(Select)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0.f, 0.f, 14.f, 0.f)
			[
				SNew(SBox).WidthOverride(36.f).HeightOverride(36.f)
				[
					SNew(SBorder).BorderImage_Lambda([this, I]() { return Rounded(Pending.LaunchSpot == I ? Accent : Chart, 18.f); }).HAlign(HAlign_Center).VAlign(VAlign_Center)
					[ SNew(STextBlock).Text(FText::AsNumber(I + 1)).Font(Font(EType::Value)).ColorAndOpacity_Lambda([this, I]() { return FSlateColor(Pending.LaunchSpot == I ? AccentInk : Fg); }) ]
				]
			]
			+ SHorizontalBox::Slot().FillWidth(1.f)
			[
				SNew(SVerticalBox)
				+ SVerticalBox::Slot().AutoHeight()
				[
					SNew(SHorizontalBox)
					+ SHorizontalBox::Slot().FillWidth(1.f)[ SailUI::Text(S.Name, EType::Ui, Fg) ]
					+ SHorizontalBox::Slot().AutoWidth()[ Pill(S.Tag, S.Tag == TEXT("Home")) ]
				]
				+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 4.f, 0.f, 0.f)[ SailUI::Text(S.Detail, EType::Small, Muted) ]
			]
		];
		List->AddSlot().AutoHeight().Padding(0.f, 0.f, 0.f, 10.f)[ Row ];
		Rows.Add(Row);
	}
	TSharedRef<SSailButton> Next = ActionButton(TEXT("Next: boat"), FSimpleDelegate::CreateLambda([this]() { Push(ESailScreen::Boat); }));
	List->AddSlot().AutoHeight().Padding(0.f, 10.f, 0.f, 0.f)[ Next ];
	E.Focus = Rows.IsValidIndex(Pending.LaunchSpot) ? Rows[Pending.LaunchSpot] : TSharedPtr<SWidget>(Next);
	E.Content = SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight()[ Header(W.Name, TEXT("Where do you start?"), 2) ]
		+ SVerticalBox::Slot().FillHeight(1.f).Padding(0.f, 24.f, 0.f, 90.f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().FillWidth(0.6f).Padding(0.f, 0.f, 24.f, 0.f)
			[
				SNew(SBorder).BorderImage(Rounded(Land, RadiusCard, Line, 1.f)).Padding(4.f)
				[
					SNew(SScaleBox).Stretch(EStretch::ScaleToFit)
					[
						SNew(SBox).WidthOverride(MapSize.X).HeightOverride(MapSize.Y)
						[
							SNew(SOverlay)
							+ SOverlay::Slot()[ SNew(SImage).Image_Lambda([Map]() { return Map.Get(); }) ]
							+ SOverlay::Slot()[ Pins ]
						]
					]
				]
			]
			+ SHorizontalBox::Slot().FillWidth(0.4f)[ SNew(SScrollBox) + SScrollBox::Slot()[ List ] ]
		];
	E.Footer = PromptBar({ Prompt(TEXT("Enter"), TEXT("A"), TEXT("Choose")), Prompt(TEXT("Esc"), TEXT("B"), TEXT("Back")) }, TEXT("Map from the game's own terrain and charts"));
	return E;
}

// ---------------------------------------------------------------- 5.4 Boat

SSailFrontEnd::FEntry SSailFrontEnd::BuildBoat()
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	FEntry E;
	// Inputs/ui-showroom/brief.md section 2 (car-select layout): the boat owns the middle of the screen; her name big on
	// the left, her numbers as bars scaled to the fleet on the right, the fleet as a strip along the bottom. Focus is the
	// selection: moving along the strip shows that boat (FSailShowroom swaps her in, debounced). Career 1: a locked boat
	// can still be looked at, but not chosen; her card and the Next button say which certificate opens her.
	const FCareerProgress Career = SailCareer::Progress();
	if (!Career.IsBoatOpen(FSailSave::BoatId(Pending.Boat))) Pending.Boat = 0;
	FocusedBoat = Pending.Boat;
	bViewMode = false;
	BoatCards.Reset();
	BoatCardTypes.Reset();
	const TArray<SailCatalog::FBoat>& Fleet = SailCatalog::Boats();
	float MaxLen = 1.f, MaxBeam = 1.f, MaxKg = 1.f, MaxKn = 1.f;
	for (const SailCatalog::FBoat& B : Fleet) if (B.Type != int32(Sailing::EBoatType::Maxi)) { MaxLen = FMath::Max(MaxLen, B.LengthM); MaxBeam = FMath::Max(MaxBeam, B.BeamM); MaxKg = FMath::Max(MaxKg, B.WeightKg); MaxKn = FMath::Max(MaxKn, B.CloseHauledKn); }
	auto Cur = [this]() -> const SailCatalog::FBoat& { return SailCatalog::Boat(FocusedBoat); };
	auto Attr = [Cur](TFunction<FString(const SailCatalog::FBoat&)> F) { return TAttribute<FText>::CreateLambda([Cur, F]() { return FText::FromString(F(Cur())); }); };
	auto LockOf = [Career](int32 T) { return Career.BoatLockReason(FSailSave::BoatId(T)); };
	auto Panels = [this]() { return bViewMode ? EVisibility::Hidden : EVisibility::Visible; };

	// The strip: eight compact cards, LB/RB (and Q/E) at its ends.
	TSharedRef<SHorizontalBox> Strip = SNew(SHorizontalBox);
	Strip->AddSlot().AutoWidth().VAlign(VAlign_Center).Padding(0.f, 0.f, 8.f, 0.f)
	[ SNew(SSailButton).Look(EButtonLook::MenuItem).Padding(FMargin(6.f, 2.f)).OnClicked_Lambda([this]() { StepBoat(-1); })[ KeyCap(TEXT("Q"), TEXT("LB")) ] ];
	for (const SailCatalog::FBoat& B : Fleet)
	{
		const int32 T = B.Type;
		// The fleet of eight: the prologue's maxi isn't in the strip (brief section 8).
		if (T == int32(Sailing::EBoatType::Maxi)) continue;
		const FString Locked = LockOf(T);
		TSharedRef<SSailButton> Card = SNew(SSailButton).Padding(FMargin(8.f, 6.f))
			.IsSelected_Lambda([this, T]() { return FocusedBoat == T; })
			.OnFocused_Lambda([this, T]() { FocusedBoat = T; })
			.OnClicked_Lambda([this, T, Locked]()
			{
				// A click shows her; a click on the boat shown moves on (as Enter does), unless she is locked.
				if (FocusedBoat != T) { FocusedBoat = T; return; }
				if (Locked.IsEmpty()) { Pending.Boat = T; Push(ESailScreen::Conditions); }
			})
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)[ SNew(SBox).WidthOverride(120.f).HeightOverride(50.f)[ SNew(SBoatIcon).Type(T) ] ]
			+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0.f, 4.f, 0.f, 0.f)[ SailUI::Text(B.Name, EType::Label, Locked.IsEmpty() ? Fg : Muted) ]
			+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)
			[
				// Her meshes loading (brief section 5's spinner), or the lock.
				TextAttr(TAttribute<FText>::CreateLambda([this, T, Locked]()
				{
					const ASailboatPawn* P = Pawn();
					if (P && P->GetShowroomLoadingType() == T)
					{
						static const TCHAR* Dots[] = { TEXT("Loading ·"), TEXT("Loading · ·"), TEXT("Loading · · ·") };
						return FText::FromString(Dots[int32(FPlatformTime::Seconds() * 4.0) % 3]);
					}
					return FText::FromString(Locked.IsEmpty() ? FString() : FString(TEXT("Locked")));
				}), EType::Small, FSlateColor(Muted))
			]
		];
		BoatCards.Add(Card);
		BoatCardTypes.Add(T);
		Strip->AddSlot().FillWidth(1.f).Padding(4.f, 0.f)[ Card ];
		if (T == Pending.Boat) E.Focus = Card;
	}
	Strip->AddSlot().AutoWidth().VAlign(VAlign_Center).Padding(8.f, 0.f, 0.f, 0.f)
	[ SNew(SSailButton).Look(EButtonLook::MenuItem).Padding(FMargin(6.f, 2.f)).OnClicked_Lambda([this]() { StepBoat(1); })[ KeyCap(TEXT("E"), TEXT("RB")) ] ];

	// Left column: type line, her name big, the pill, the description, the flags.
	FSlateFontInfo NameFont = Font(EType::Logo);
	NameFont.Size = 80;
	TSharedRef<SWidget> Left = SNew(SBox).WidthOverride(380.f)
	[
		SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight()[ SNew(SBox).Visibility_Lambda(Panels)[ TextAttr(Attr([](const SailCatalog::FBoat& B) { return B.TypeLine.ToUpper(); }), EType::Eyebrow, FSlateColor(Accent)) ] ]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 2.f, 0.f, 8.f)
		[
			SNew(STextBlock).Font(NameFont).ColorAndOpacity(Fg).AutoWrapText(true).LineHeightPercentage(0.85f)
				.Text_Lambda([Cur]() { return FText::FromString(Cur().Name.ToUpper()); })
		]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 0.f, 0.f, 12.f)
		[
			SNew(SBox).Visibility_Lambda([this, Panels]() { return Panels() == EVisibility::Visible && (FocusedBoat == 0 || !SailCareer::Progress().BoatLockReason(FSailSave::BoatId(FocusedBoat)).IsEmpty()) ? EVisibility::Visible : EVisibility::Collapsed; })
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().AutoWidth()[ SNew(SBox).Visibility_Lambda([this]() { return FocusedBoat == 0 ? EVisibility::Visible : EVisibility::Collapsed; })[ Pill(TEXT("Your lesson boat"), true) ] ]
				+ SHorizontalBox::Slot().FillWidth(1.f)
				[
					TextAttr(TAttribute<FText>::CreateLambda([this, LockOf]() { return FText::FromString(LockOf(FocusedBoat)); }), EType::Small, FSlateColor(Fg), true)
				]
			]
		]
		+ SVerticalBox::Slot().AutoHeight()[ SNew(SBox).Visibility_Lambda(Panels)[ TextAttr(Attr([](const SailCatalog::FBoat& B) { return B.Description; }), EType::Body, FSlateColor(Muted), true) ] ]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 14.f, 0.f, 0.f)
		[
			SNew(SBox).Visibility_Lambda(Panels)[ TextAttr(Attr([](const SailCatalog::FBoat& B) { return FString::Join(B.Flags, TEXT("   ·   ")).ToUpper(); }), EType::Label, FSlateColor(Fg), true) ]
		]
	];

	// Right column: the numbers as bars against the fleet's biggest, the handling, the note, Next.
	auto Bar = [&](const FString& Label, TFunction<FString(const SailCatalog::FBoat&)> Value, TFunction<float(const SailCatalog::FBoat&)> Share)
	{
		return SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().FillWidth(1.f)[ SailUI::Text(Label, EType::Ui, Muted) ]
				+ SHorizontalBox::Slot().AutoWidth()[ TextAttr(Attr(Value), EType::Value, FSlateColor(Fg)) ]
			]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 5.f, 0.f, 12.f)
			[
				SNew(SBox).HeightOverride(4.f)
				[
					SNew(SOverlay)
					+ SOverlay::Slot()[ SNew(SBorder).BorderImage(Rounded(Line, 2.f)) ]
					+ SOverlay::Slot().HAlign(HAlign_Left)
					[
						SNew(SBox).WidthOverride_Lambda([Cur, Share]() { return FOptionalSize(FMath::Clamp(Share(Cur()), 0.03f, 1.f) * 280.f); })
						[ SNew(SBorder).BorderImage(Rounded(Accent, 2.f)) ]
					]
				]
			];
	};
	TSharedRef<SHorizontalBox> Pips = SNew(SHorizontalBox);
	for (int32 K = 1; K <= 5; ++K)
	{
		Pips->AddSlot().AutoWidth().Padding(2.f, 0.f)[ SNew(SBox).WidthOverride(22.f).HeightOverride(6.f)[ SNew(SBorder).BorderImage_Lambda([Cur, K]() { return Rounded(Cur().Handling >= K ? Accent : Line, 2.f); }) ] ];
	}
	TSharedRef<SSailButton> Next = ActionButton(TEXT("Next: conditions"), FSimpleDelegate::CreateLambda([this, LockOf]()
	{
		if (!LockOf(FocusedBoat).IsEmpty()) return;
		Pending.Boat = FocusedBoat;
		Push(ESailScreen::Conditions);
	}));
	TSharedRef<SWidget> Right = SNew(SBox).WidthOverride(330.f).Visibility_Lambda(Panels)
	[
		PanelBox(SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()[ Bar(TEXT("Length"), [](const SailCatalog::FBoat& B) { return B.Length; }, [MaxLen](const SailCatalog::FBoat& B) { return B.LengthM / MaxLen; }) ]
			+ SVerticalBox::Slot().AutoHeight()[ Bar(TEXT("Beam"), [](const SailCatalog::FBoat& B) { return B.Beam; }, [MaxBeam](const SailCatalog::FBoat& B) { return B.BeamM / MaxBeam; }) ]
			+ SVerticalBox::Slot().AutoHeight()[ Bar(TEXT("Weight"), [](const SailCatalog::FBoat& B) { return B.Weight; }, [MaxKg](const SailCatalog::FBoat& B) { return B.WeightKg / MaxKg; }) ]
			+ SVerticalBox::Slot().AutoHeight()[ Bar(TEXT("Close-hauled at 12 kn"), [](const SailCatalog::FBoat& B) { return B.CloseHauled; }, [MaxKn](const SailCatalog::FBoat& B) { return B.CloseHauledKn / MaxKn; }) ]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 0.f, 0.f, 14.f)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().FillWidth(1.f)[ SailUI::Text(TEXT("Handling"), EType::Ui, Muted) ]
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)[ Pips ]
			]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 0.f, 0.f, 16.f)[ SailUI::Text(TEXT("Speeds are the boat's reference polar at 12 kn true wind."), EType::Small, Muted, true) ]
			+ SVerticalBox::Slot().AutoHeight()[ SNew(SBox).IsEnabled_Lambda([this, LockOf]() { return LockOf(FocusedBoat).IsEmpty(); })[ Next ] ],
			FMargin(22.f))
	];

	// Under the boat: where the camera stands, the turn buttons for the mouse, the auto spin switch, the reset.
	auto ViewName = [this]() -> FText
	{
		const ASailboatPawn* P = Pawn();
		const float B = P ? P->GetShowroomViewBearing() : 135.f;
		const float A = FMath::Abs(B);
		const TCHAR* Side = B >= 0.f ? TEXT("starboard") : TEXT("port");
		const FString Where = A < 22.5f ? FString(TEXT("ahead")) : (A > 157.5f ? FString(TEXT("astern"))
			: FString::Printf(TEXT("%s %s"), Side, A < 67.5f ? TEXT("bow") : (A < 112.5f ? TEXT("beam") : TEXT("quarter"))));
		return FText::FromString(FString::Printf(TEXT("View from %s"), *Where));
	};
	TSharedRef<SWidget> Orbit = SNew(SBox).Visibility_Lambda(Panels)
	[
		SNew(SHorizontalBox)
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
		[ SNew(SSailButton).Look(EButtonLook::Secondary).Padding(FMargin(12.f, 4.f)).OnClicked_Lambda([this]() { if (ASailboatPawn* P = Pawn()) P->ShowroomLook(FVector2D(-30.0, 0.0)); })[ SailUI::Text(TEXT("←"), EType::Ui, Fg) ] ]
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(14.f, 0.f)[ SNew(SBox).MinDesiredWidth(230.f).HAlign(HAlign_Center)[ TextAttr(TAttribute<FText>::CreateLambda(ViewName), EType::Label, FSlateColor(Fg)) ] ]
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
		[ SNew(SSailButton).Look(EButtonLook::Secondary).Padding(FMargin(12.f, 4.f)).OnClicked_Lambda([this]() { if (ASailboatPawn* P = Pawn()) P->ShowroomLook(FVector2D(30.0, 0.0)); })[ SailUI::Text(TEXT("→"), EType::Ui, Fg) ] ]
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(18.f, 0.f, 6.f, 0.f)
		[
			SNew(SSailButton).Look(EButtonLook::Chip).Padding(FMargin(12.f, 4.f))
				.IsSelected_Lambda([this]() { const ASailboatPawn* P = Pawn(); return P && P->GetShowroomAutoSpin(); })
				.OnClicked_Lambda([this]() { if (ASailboatPawn* P = Pawn()) P->SetShowroomAutoSpin(!P->GetShowroomAutoSpin()); })
			[ TextAttr(TAttribute<FText>::CreateLambda([this]() { const ASailboatPawn* P = Pawn(); return FText::FromString(P && P->GetShowroomAutoSpin() ? TEXT("Auto spin on") : TEXT("Auto spin off")); }), EType::Label,
				TAttribute<FSlateColor>::CreateLambda([this]() { const ASailboatPawn* P = Pawn(); return FSlateColor(P && P->GetShowroomAutoSpin() ? Ink : Fg); })) ]
		]
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(6.f, 0.f)
		[ SNew(SSailButton).Look(EButtonLook::Secondary).Padding(FMargin(12.f, 4.f)).OnClicked_Lambda([this]() { if (ASailboatPawn* P = Pawn()) P->ShowroomResetView(); })[ SailUI::Text(TEXT("Reset view"), EType::Label, Fg) ] ]
	];

	FSlateFontInfo TitleFont = Font(EType::ScreenTitle);
	TitleFont.Size = 44;
	E.Content = SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight()
		[
			SNew(SOverlay).Visibility_Lambda(Panels)
			+ SOverlay::Slot()[ Header(FString(), FString(), 3) ]
			+ SOverlay::Slot().HAlign(HAlign_Left).VAlign(VAlign_Bottom)
			[
				SNew(SVerticalBox)
				+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(TEXT("Fleet of eight"), EType::Eyebrow, Accent) ]
				+ SVerticalBox::Slot().AutoHeight()[ SNew(STextBlock).Font(TitleFont).ColorAndOpacity(Fg).Text(FText::FromString(TEXT("CHOOSE A BOAT"))) ]
			]
		]
		+ SVerticalBox::Slot().FillHeight(1.f).Padding(0.f, 22.f, 0.f, 0.f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Top)[ Left ]
			+ SHorizontalBox::Slot().FillWidth(1.f).HAlign(HAlign_Center).VAlign(VAlign_Bottom).Padding(16.f, 0.f, 16.f, 10.f)[ Orbit ]
			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Top)[ Right ]
		]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 8.f, 0.f, 92.f)[ SNew(SBox).Visibility_Lambda(Panels)[ Strip ] ];
	E.Footer = PromptBar({ Prompt(TEXT("Enter"), TEXT("A"), TEXT("Choose")), Prompt(TEXT("Q / E"), TEXT("LB / RB"), TEXT("Boat")),
		Prompt(TEXT("Drag"), TEXT("R"), TEXT("Turn")), Prompt(TEXT("Wheel"), TEXT("LT / RT"), TEXT("Zoom")), Prompt(TEXT("V"), TEXT("View"), TEXT("Hide panels")),
		Prompt(TEXT("Esc"), TEXT("B"), TEXT("Back")) }, FString());
	return E;
}

// ---------------------------------------------------------------- 5.5 Conditions

SSailFrontEnd::FEntry SSailFrontEnd::BuildConditions(bool bInGame)
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	FEntry E;
	// Inputs/ui-showroom/brief.md section 6 (artboard 3): the world behind is the preview, so every control lives in one
	// translucent column on the left (presets in two columns, then the rows) and the rest of the screen is the sky, the
	// water and the boat under the conditions being set, with a "Live preview" badge, the wind near the boat and "What to
	// expect" as a caption. V or View hides the column for a full look; a drag or the right stick looks around.
	bViewMode = false;
	FSailConditions* C = &Pending.Conditions;
	auto Touch = [this]() { Pending.Conditions.PresetId = NAME_None; Pending.Conditions.RealDay.Empty(); };
	const bool bGalveston = Pending.World == 1;
	auto Panels = [this]() { return bViewMode ? EVisibility::Hidden : EVisibility::Visible; };
	TSharedRef<SUniformGridPanel> Presets = SNew(SUniformGridPanel).SlotPadding(FMargin(4.f));
	int32 Slot = 0;
	for (const FSailPreset& P : USailSessionSubsystem::Presets())
	{
		const bool bOk = !P.bGalvestonOnly || bGalveston;
		TSharedRef<SSailButton> B = SNew(SSailButton).Padding(FMargin(12.f, 8.f)).IsEnabled(bOk)
			.IsSelected_Lambda([this, Id = P.Id]() { return Pending.Conditions.PresetId == Id; })
			.OnClicked_Lambda([this, P, bInGame]()
			{
				// Confirm on the preset already chosen moves on (as on the launch spots and boats).
				if (Pending.Conditions.PresetId == P.Id && !bInGame) Push(ESailScreen::Mode);
				else USailSessionSubsystem::ApplyPreset(Pending.Conditions, P);
			})
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(P.Name, EType::Ui, Fg) ]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 2.f, 0.f, 0.f)[ SailUI::Text(bOk ? P.Summary : FString(TEXT("Galveston only")), EType::Small, Muted, true) ]
		];
		Presets->AddSlot(Slot % 2, Slot / 2)[ B ];
		++Slot;
		if (!E.Focus.IsValid()) E.Focus = B;
	}
	// W5b: real days (HRRR timeline, radar replay of a storm), Lake Ray Hubbard only. Choosing one sets its date and start;
	// the wind, gusts and sky are the day's own (touching them leaves the real day).
	TSharedRef<SUniformGridPanel> Days = SNew(SUniformGridPanel).SlotPadding(FMargin(4.f));
	Slot = 0;
	for (const SailCatalog::FRealDay& D : SailCatalog::RealDays())
	{
		const bool bOk = Pending.World == 0;
		TSharedRef<SSailButton> B = SNew(SSailButton).Padding(FMargin(12.f, 8.f)).IsEnabled(bOk)
			.IsSelected_Lambda([this, Date = D.Date]() { return Pending.Conditions.RealDay == Date; })
			.OnClicked_Lambda([this, D, bInGame]()
			{
				if (Pending.Conditions.RealDay == D.Date && !bInGame) { Push(ESailScreen::Mode); return; }
				FSailConditions& K = Pending.Conditions;
				K.RealDay = D.Date;
				K.PresetId = NAME_None;
				K.LocalHour = FMath::Clamp(D.StartHour, 5.f, 22.f);
				K.Month = D.Month;
				K.Day = D.Day;
				K.Sky = D.bStorm ? ESailSky::Storms : ESailSky::Fair;
			})
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(D.Title, EType::Ui, Fg, true) ]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 2.f, 0.f, 0.f)[ SailUI::Text(bOk ? D.Summary : FString(TEXT("Lake Ray Hubbard only")), EType::Small, Muted, true) ]
		];
		Days->AddSlot(Slot % 2, Slot / 2)[ B ];
		++Slot;
	}
	auto Kn = [](float V) { return FString::Printf(TEXT("%.0f kn"), V); };
	// Each row is a slot of the column's scroll box: it navigates from slot to slot, so rows sharing one slot were
	// skipped going up.
	TArray<TSharedRef<SWidget>> Rows;
	auto Row = [&](TSharedRef<SWidget> W) { Rows.Add(W); };
	Row(SNew(SSailSlider).Label(TEXT("Wind speed")).Min(0.f).Max(30.f).Step(1.f).Value_Lambda([C]() { return C->WindKn; })
		.ValueText_Lambda([C, Kn]() { return Kn(C->WindKn); }).OnChanged_Lambda([C, Touch](float V) { C->WindKn = V; C->GustKn = FMath::Max(C->GustKn, V); Touch(); }));
	Row(SNew(SSailSlider).Label(TEXT("Gusts to")).Min(0.f).Max(40.f).Step(1.f).Value_Lambda([C]() { return C->GustKn; })
		.ValueText_Lambda([C, Kn]() { return Kn(C->GustKn); }).OnChanged_Lambda([C, Touch](float V) { C->GustKn = FMath::Max(V, C->WindKn); Touch(); }));
	// (The wind dial was too big for one column: the direction is a slider here, its compass point beside it.)
	Row(SNew(SSailSlider).Label(TEXT("Wind from")).Min(0.f).Max(355.f).Step(5.f).Value_Lambda([C]() { return C->WindFromDeg; })
		.ValueText_Lambda([C]() { return FString::Printf(TEXT("%s  %03.0f°"), *USailSessionSubsystem::CompassPoint(C->WindFromDeg), C->WindFromDeg); })
		.OnChanged_Lambda([C, Touch](float V) { C->WindFromDeg = V; Touch(); }));
	Row(SNew(SSailChoice).Label(TEXT("Sky")).Options({ TEXT("Clear"), TEXT("Fair"), TEXT("Overcast"), TEXT("Rain"), TEXT("Storms"), TEXT("Fog") })
		.Index_Lambda([C]() { return SailFrontEndImpl::SkyRowOrder.IndexOfByKey(C->Sky); })
		.OnChanged_Lambda([C, Touch](int32 I) { C->Sky = SailFrontEndImpl::SkyRowOrder[FMath::Clamp(I, 0, SailFrontEndImpl::SkyRowOrder.Num() - 1)]; Touch(); }));
	Row(SNew(SSailSlider).Label(TEXT("Time of day")).Min(5.f).Max(22.f).Step(0.25f).Value_Lambda([C]() { return C->LocalHour; })
		.ValueText_Lambda([C]() { return SailCatalog::ClockText(C->LocalHour); }).OnChanged_Lambda([C](float V) { C->LocalHour = V; C->PresetId = NAME_None; }));
	Row(SNew(SSailSlider).Label(TEXT("Date")).Min(1.f).Max(12.f).Step(1.f).Value_Lambda([C]() { return float(C->Month); })
		.ValueText_Lambda([C]() { return FString::Printf(TEXT("%s %d"), *SailCatalog::MonthName(C->Month), C->Day); })
		.OnChanged_Lambda([C, Touch](float V) { C->Month = FMath::RoundToInt(V); C->Day = FMath::Min(C->Day, 28); Touch(); }));
	Row(SNew(SSailSlider).Label(TEXT("Air temp")).Min(30.f).Max(105.f).Step(1.f).Value_Lambda([C]() { return C->AirTempF; })
		.ValueText_Lambda([C]() { return FString::Printf(TEXT("%.0f°F"), C->AirTempF); }).OnChanged_Lambda([C, Touch](float V) { C->AirTempF = V; Touch(); }));
	if (bGalveston)
	{
		Row(SailUI::Text(TEXT("Tide: predicted from NOAA's harmonic constants for the date and time you pick; the tide and current follow the clock."), EType::Small, Muted, true));
	}
	else
	{
		Row(SNew(SSailSlider).Label(TEXT("Lake level")).Min(-6.f).Max(3.f).Step(0.5f).Value_Lambda([C]() { return C->LakeLevelFt; })
			.ValueText_Lambda([C]() { return FString::Printf(TEXT("%+.1f ft"), C->LakeLevelFt); }).OnChanged_Lambda([C](float V) { C->LakeLevelFt = V; }));
	}
	TSharedRef<SSailButton> Next = bInGame
		? ActionButton(TEXT("Apply"), FSimpleDelegate::CreateLambda([this]()
			{
				if (ASailingGameMode* GM = Player.IsValid() ? Player->GetWorld()->GetAuthGameMode<ASailingGameMode>() : nullptr) GM->ApplyConditions(Pending.Conditions);
				Pop();
			}))
		: ActionButton(TEXT("Next: mode"), FSimpleDelegate::CreateLambda([this]() { Push(ESailScreen::Mode); }));
	FSlateFontInfo TitleFont = Font(EType::ScreenTitle);
	TitleFont.Size = 40;
	// Keys and the pad move focus down the column: it scrolls to keep the focused row in view (rows under the fold are out
	// of the hit-test grid that navigation searches: Down used to stop at the sky).
	TSharedRef<SScrollBox> Scroll = SNew(SScrollBox).ScrollBarThickness(FVector2D(4.f, 4.f))
		.ScrollWhenFocusChanges(EScrollWhenFocusChanges::AnimatedScroll).NavigationScrollPadding(24.f)
		+ SScrollBox::Slot().Padding(0.f, 0.f, 10.f, 0.f)[ Presets ]
		+ SScrollBox::Slot().Padding(4.f, 8.f, 14.f, 2.f)[ SailUI::Text(TEXT("Real day"), EType::Label, Muted) ]
		+ SScrollBox::Slot().Padding(0.f, 0.f, 10.f, 12.f)[ Days ];
	for (const TSharedRef<SWidget>& R : Rows) Scroll->AddSlot().Padding(4.f, 0.f, 14.f, 8.f)[ R ];
	TSharedRef<SWidget> Column = SNew(SBox).WidthOverride(540.f).Visibility_Lambda(Panels)
	[
		PanelBox(SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(bInGame ? TEXT("Paused") : TEXT("Weather and time"), EType::Eyebrow, Accent) ]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 0.f, 0.f, 10.f)
			[ SNew(STextBlock).Font(TitleFont).ColorAndOpacity(Fg).Text(FText::FromString(bInGame ? TEXT("CHANGE CONDITIONS") : TEXT("SET THE CONDITIONS"))) ]
			+ SVerticalBox::Slot().FillHeight(1.f)
			[
				Scroll
			]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 10.f, 0.f, 0.f)[ Next ],
			FMargin(22.f, 18.f))
	];
	// Over the world: the badge (the clock the preview shows), the wind near the boat, the caption.
	auto Badge = PanelBox(SNew(SHorizontalBox)
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0.f, 0.f, 8.f, 0.f)[ SNew(SBox).WidthOverride(8.f).HeightOverride(8.f)[ SNew(SBorder).BorderImage(Rounded(Accent, 4.f)) ] ]
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
		[ TextAttr(TAttribute<FText>::CreateLambda([this]() { return FText::FromString(FString::Printf(TEXT("LIVE PREVIEW  ·  %s"), *SailCatalog::ClockText(bBlendLive ? Blend.LocalHour : Pending.Conditions.LocalHour))); }), EType::Label, FSlateColor(Fg)) ],
		FMargin(14.f, 8.f));
	TSharedRef<SWidget> WindLine = TextAttr(TAttribute<FText>::CreateLambda([this]()
	{
		const FSailConditions& K = bBlendLive ? Blend : Pending.Conditions;
		if (!K.RealDay.IsEmpty()) return FText::FromString(FString::Printf(TEXT("The day's own wind  ·  %s"), *K.RealDay));
		return FText::FromString(FString::Printf(TEXT("↓ %.0f kn from %s, gusts to %.0f"), K.WindKn, *USailSessionSubsystem::CompassPoint(K.WindFromDeg), K.GustKn));
	}), EType::Ui, FSlateColor(Fg));
	TSharedRef<SWidget> Expect = SNew(SBox).WidthOverride(440.f).Visibility_Lambda(Panels)
	[
		PanelBox(SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(TEXT("What to expect"), EType::Label, Muted) ]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 6.f, 0.f, 0.f)
			[
				TextAttr(TAttribute<FText>::CreateLambda([this]()
				{
					const FSailConditions& K = Pending.Conditions;
					return FText::FromString(SailCatalog::Expect(K.WindKn, K.GustKn, int32(K.Sky), K.LocalHour, K.Month, K.Day, Pending.Boat, Pending.World));
				}), EType::Body, FSlateColor(Fg), true)
			], FMargin(16.f))
	];
	E.Content = SNew(SOverlay)
		+ SOverlay::Slot().HAlign(HAlign_Left).Padding(0.f, 0.f, 0.f, 92.f)[ Column ]
		+ SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Top)[ Badge ]
		+ SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Bottom).Padding(0.f, 0.f, 0.f, 92.f)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Right).Padding(0.f, 0.f, 0.f, 12.f)[ WindLine ]
			+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Right)[ Expect ]
		];
	E.Footer = PromptBar({ Prompt(TEXT("Enter"), TEXT("A"), bInGame ? TEXT("Apply") : TEXT("Next")), Prompt(TEXT("← →"), TEXT("← →"), TEXT("Adjust")),
		Prompt(TEXT("Drag"), TEXT("R"), TEXT("Look")), Prompt(TEXT("V"), TEXT("View"), TEXT("Hide panel")), Prompt(TEXT("Esc"), TEXT("B"), TEXT("Back")) },
		TEXT("The world behind is the preview: the wind eases in; the sky changes once you stop"));
	return E;
}

// ---------------------------------------------------------------- 5.6 Mode

SSailFrontEnd::FEntry SSailFrontEnd::BuildMode()
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	FEntry E;
	struct FModeCard { ESailMode Mode; const TCHAR* Name; const TCHAR* Line; };
	static const FModeCard Modes[] = { { ESailMode::Free, TEXT("Free sail"), TEXT("Go where you like") },
		{ ESailMode::Drill, TEXT("ASA 101 drills"), TEXT("Six graded drills") }, { ESailMode::Race, TEXT("Race"), TEXT("Five AI boats, a 5-minute start") },
		{ ESailMode::Passage, TEXT("Passage"), TEXT("Galveston entrance to Freeport") } };
	TSharedRef<SHorizontalBox> Cards = SNew(SHorizontalBox);
	for (const FModeCard& M : Modes)
	{
		// Passage: Galveston's to Freeport (the Gulf world, its own career lock) or Marseille's to Cassis.
		const FString GulfLocked = Pending.World == 1 ? SailCareer::Progress().WorldLockReason(FSailSave::WorldId(2)) : FString();
		const bool bOk = M.Mode != ESailMode::Passage || (USailSessionSubsystem::HasPassage(Pending.World) && GulfLocked.IsEmpty());
		const FString ModeLine = (M.Mode == ESailMode::Passage && Pending.World == 3) ? FString(TEXT("Vieux-Port to Cassis by the Calanques")) : FString(M.Line);
		const ESailMode Mode = M.Mode;
		TSharedRef<SSailButton> B = SNew(SSailButton).Padding(FMargin(18.f, 16.f)).IsEnabled(bOk).IsSelected_Lambda([this, Mode]() { return Pending.Mode == Mode; })
			.OnClicked_Lambda([this, Mode]() { Pending.Mode = Mode; Stack.Last() = Build(ESailScreen::Mode); Show(Stack.Last(), true); })
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(M.Name, EType::CardTitleS, Fg) ]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 4.f, 0.f, 0.f)[ SailUI::Text(bOk ? ModeLine : (!USailSessionSubsystem::HasPassage(Pending.World) ? FString(TEXT("Galveston and Marseille only")) : GulfLocked), EType::Small, Muted) ]
		];
		Cards->AddSlot().FillWidth(1.f).Padding(0.f, 0.f, 12.f, 0.f)[ B ];
		if (M.Mode == Pending.Mode) E.Focus = B;
	}
	TSharedRef<SWidget> Context = SNullWidget::NullWidget;
	if (Pending.Mode == ESailMode::Drill)
	{
		TSharedRef<SUniformGridPanel> Drills = SNew(SUniformGridPanel).SlotPadding(FMargin(6.f));
		const USailSessionSave* Save = USailSessionSave::Get();
		for (int32 I = 0; I < 6; ++I)
		{
			Drills->AddSlot(I % 3, I / 3)
			[
				SNew(SSailButton).Look(EButtonLook::Card).Padding(FMargin(14.f, 10.f)).IsSelected_Lambda([this, I]() { return Pending.DrillIndex == I; })
				.OnClicked_Lambda([this, I]() { Pending.DrillIndex = I; })
				[
					SNew(SHorizontalBox)
					+ SHorizontalBox::Slot().FillWidth(1.f)[ SailUI::Text(FString::Printf(TEXT("%d. %s"), I + 1, DrillName(ESailingDrill(I + 1))), EType::Ui, Fg) ]
					+ SHorizontalBox::Slot().AutoWidth()[ SailUI::Text(Save->DrillsPassed.Contains(I) ? TEXT("Passed") : TEXT("Not yet"), EType::Label, Save->DrillsPassed.Contains(I) ? Starboard : Dim) ]
				]
			];
		}
		Context = Drills;
	}
	else if (Pending.Mode == ESailMode::Race)
	{
		Context = PanelBox(SailUI::Text(FString::Printf(TEXT("Windward-leeward, 2 laps · five AI boats · %s · the Racing Rules apply"), *SailCatalog::Boat(Pending.Boat).Name), EType::Body, Fg), FMargin(16.f, 12.f));
	}
	else if (Pending.Mode == ESailMode::Passage)
	{
		Context = PanelBox(SailUI::Text(Pending.World == 3
			? TEXT("Vieux-Port → Cassis, 18 nm: past the Château d'If, outside Maïre and Riou, along the Calanques. Plot fixes on the chart (P) as you go.")
			: TEXT("Galveston entrance → Freeport, 45 nm along the coast. Plot fixes on the chart (P) as you go."), EType::Body, Fg), FMargin(16.f, 12.f));
	}
	auto Seg = [](const FString& Label, TArray<FString> Opts, TFunction<int32()> Get, TFunction<void(int32)> Set, bool bEnabled = true, const FString& Note = FString())
	{
		return SNew(SSailChoice).Label(Label).Options(Opts).Index_Lambda([Get]() { return Get(); }).OnChanged_Lambda([Set](int32 I) { Set(I); }).IsEnabled(bEnabled).Note(Note);
	};
	const bool bTipsOk = Pending.bLearningMode;
	TSharedRef<SGridPanel> Toggles = SNew(SGridPanel).FillColumn(0, 1.f).FillColumn(1, 1.f);
	Toggles->AddSlot(0, 0).Padding(0.f, 0.f, 10.f, 10.f)[ Seg(TEXT("Mode"), { TEXT("Learning"), TEXT("Game") }, [this]() { return Pending.bLearningMode ? 0 : 1; },
		[this](int32 I) { Pending.bLearningMode = I == 0; if (!Pending.bLearningMode) Pending.bLearningTips = false; Stack.Last() = Build(ESailScreen::Mode); Show(Stack.Last(), true); }) ];
	Toggles->AddSlot(1, 0).Padding(0.f, 0.f, 0.f, 10.f)[ Seg(TEXT("Difficulty"), { TEXT("Easy sailing"), TEXT("Realistic") }, [this]() { return Pending.bEasy ? 0 : 1; }, [this](int32 I) { Pending.bEasy = I == 0; }) ];
	Toggles->AddSlot(0, 1).Padding(0.f, 0.f, 10.f, 0.f)[ Seg(TEXT("Learning tips"), { TEXT("On"), TEXT("Off") }, [this]() { return Pending.bLearningTips ? 0 : 1; },
		[this](int32 I) { Pending.bLearningTips = I == 0; }, bTipsOk, bTipsOk ? FString() : FString(TEXT("Tips off in Game mode"))) ];
	Toggles->AddSlot(1, 1)[ Seg(TEXT("Traffic"), { TEXT("Off"), TEXT("Light"), TEXT("Busy") }, [this]() { return Pending.Traffic; }, [this](int32 I) { Pending.Traffic = I; }) ];
	const SailCatalog::FWorld& W = SailCatalog::World(Pending.World);
	const FSailConditions& C = Pending.Conditions;
	TSharedRef<SHorizontalBox> Summary = SNew(SHorizontalBox);
	auto Sum = [&](const FString& Label, const FString& Value) { Summary->AddSlot().FillWidth(1.f)[ Fact(Value, Label) ]; };
	Sum(TEXT("World"), W.Name);
	Sum(TEXT("Start"), W.Spots.IsValidIndex(Pending.LaunchSpot) ? W.Spots[Pending.LaunchSpot].Name : FString(TEXT("–")));
	Sum(TEXT("Boat"), SailCatalog::Boat(Pending.Boat).Name);
	Sum(TEXT("Wind"), FString::Printf(TEXT("%.0f kn %s, G%.0f"), C.WindKn, *USailSessionSubsystem::CompassPoint(C.WindFromDeg), C.GustKn));
	Sum(TEXT("When"), FString::Printf(TEXT("%s %d, %s"), *SailCatalog::MonthName(C.Month), C.Day, *SailCatalog::ClockText(C.LocalHour)));
	Summary->AddSlot().AutoWidth().VAlign(VAlign_Center)[ ActionButton(TEXT("Cast off"), FSimpleDelegate::CreateLambda([this]() { CastOff(); })) ];
	E.Content = SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight()[ Header(TEXT("Last step"), TEXT("How do you want to sail?"), 5) ]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 24.f, 0.f, 14.f)[ Cards ]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 0.f, 0.f, 14.f)[ Context ]
		+ SVerticalBox::Slot().AutoHeight()[ Toggles ]
		+ SVerticalBox::Slot().FillHeight(1.f)[ SNew(SSpacer) ]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 0.f, 0.f, 90.f)[ PanelBox(Summary, FMargin(20.f, 14.f)) ];
	E.Footer = PromptBar({ Prompt(TEXT("Enter"), TEXT("A"), TEXT("Choose")), Prompt(TEXT("Esc"), TEXT("B"), TEXT("Back")) }, TEXT("Cast off loads the world with these choices"));
	return E;
}

// ---------------------------------------------------------------- 5.9 Pause

SSailFrontEnd::FEntry SSailFrontEnd::BuildPause()
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	FEntry E;
	ASailboatPawn* P = Pawn();
	TSharedRef<SVerticalBox> Menu = SNew(SVerticalBox);
	TSharedPtr<SWidget> First;
	auto Item = [&](const FString& Label, const FString& Sub, FSimpleDelegate Do)
	{
		TSharedRef<SSailButton> B = SNew(SSailButton).Look(EButtonLook::MenuItem).OnClicked(Do).Padding(FMargin(18.f, 4.f))
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().FillWidth(1.f).VAlign(VAlign_Center)[ SailUI::Text(Label, EType::MenuItem, Fg) ]
			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)[ SailUI::Text(Sub, EType::Small, Muted) ]
		];
		Menu->AddSlot().AutoHeight().Padding(0.f, 1.f)[ SNew(SBox).WidthOverride(520.f)[ B ] ];
		if (!First.IsValid()) First = B;
	};
	const USailSessionSubsystem* Session = USailSessionSubsystem::Get(Player.Get());
	const ESailMode Mode = Session && Session->bHasActive ? Session->Active.Mode : ESailMode::Free;
	Item(TEXT("Resume"), FString(), FSimpleDelegate::CreateLambda([this]() { Close(); }));
	Item(Mode == ESailMode::Drill ? TEXT("Restart drill") : (Mode == ESailMode::Race ? TEXT("Restart race") : TEXT("Restart from launch spot")), FString(),
		FSimpleDelegate::CreateLambda([this, Mode]()
		{
			Confirm(TEXT("Restart? Your logbook entry is kept."), TEXT("Restart"), [this, Mode]()
			{
				if (USailSessionSubsystem* S = USailSessionSubsystem::Get(Player.Get()); S && S->bHasActive) S->StartSession(S->Active, Player.Get());
				else if (ASailboatPawn* B = Pawn()) { B->ResetBoat(); Close(); }
			});
		}));
	Item(TEXT("Change conditions"), TEXT("No reload"), FSimpleDelegate::CreateLambda([this]() { Push(ESailScreen::ConditionsInGame); }));
	Item(TEXT("Chart"), TEXT("P"), FSimpleDelegate::CreateLambda([this]() { if (ASailboatPawn* B = Pawn()) B->SetChartOpenFromUI(true); Close(); }));
	Item(TEXT("Logbook"), TEXT("Y"), FSimpleDelegate::CreateLambda([this]() { if (ASailboatPawn* B = Pawn()) B->SetLogOpen(true); Close(); }));
	Item(TEXT("Photo mode"), TEXT("9"), FSimpleDelegate::CreateLambda([this]() { Close(); if (ASailboatPawn* B = Pawn()) B->SetPhotoFromUI(true); }));
	Item(TEXT("Settings"), FString(), FSimpleDelegate::CreateLambda([this]() { Push(ESailScreen::Settings); }));
	Item(TEXT("Controls"), FString(), FSimpleDelegate::CreateLambda([this]() { Push(ESailScreen::Controls); }));
	Item(TEXT("Quit to title"), FString(), FSimpleDelegate::CreateLambda([this]()
	{
		Confirm(TEXT("Leave this session? Your logbook entry is saved."), TEXT("Leave"), [this]()
		{
			if (USailSessionSubsystem* S = USailSessionSubsystem::Get(Player.Get())) { S->bHasActive = false; S->bStarted = false; }
			UGameplayStatics::OpenLevel(Player.Get(), FName(*UGameplayStatics::GetCurrentLevelName(Player.Get())));
		});
	}));
	// Stat tiles and the coach's summary.
	double LogNm = 0.0, Top = 0.0, Minutes = 0.0;
	if (P)
	{
		const FLogbook& L = P->GetLogbook();
		if (L.GetEntries().Num()) LogNm = L.GetEntries().Last().LogNm;
		Top = L.MaxSpeedKnots;
		Minutes = P->GetBoatModel().GetState().Time / 60.0;
	}
	auto Tile = [](const FString& Value, const FString& Label)
	{
		return PanelBox(SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(Value, EType::InstrumentBig, Fg) ]
			+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(Label, EType::Label, Muted) ], FMargin(18.f, 12.f));
	};
	FString Coach = TEXT("Free sailing: practise your points of sail and tacks.");
	if (P && P->GetDrill().IsActive()) Coach = FString::Printf(TEXT("%s: %s"), DrillName(P->GetDrill().GetDrill()), P->GetDrill().GetSteps().IsValidIndex(P->GetDrill().GetStep()) ? *P->GetDrill().GetSteps()[P->GetDrill().GetStep()] : *P->GetDrill().GetStatus());
	E.Content = SNew(SHorizontalBox)
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(FString::Printf(TEXT("Paused · %.0f min on the water"), Minutes), EType::Eyebrow, Accent) ]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 4.f, 0.f, 24.f)[ SailUI::Text(USailSessionSubsystem::ModeName(Mode), EType::ScreenTitle, Fg) ]
			+ SVerticalBox::Slot().AutoHeight()[ Menu ]
		]
		+ SHorizontalBox::Slot().FillWidth(1.f)[ SNew(SSpacer) ]
		+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
		[
			SNew(SBox).WidthOverride(520.f)
			[
				SNew(SVerticalBox)
				+ SVerticalBox::Slot().AutoHeight()
				[
					SNew(SHorizontalBox)
					+ SHorizontalBox::Slot().FillWidth(1.f).Padding(0.f, 0.f, 10.f, 0.f)[ Tile(FString::Printf(TEXT("%.1f"), LogNm), TEXT("Distance nm")) ]
					+ SHorizontalBox::Slot().FillWidth(1.f)[ Tile(FString::Printf(TEXT("%.1f"), Top), TEXT("Top speed kn")) ]
				]
				+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 12.f, 0.f, 0.f)
				[
					PanelBox(SNew(SVerticalBox)
						+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(TEXT("Coach"), EType::Eyebrow, Accent) ]
						+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 6.f, 0.f, 0.f)[ SailUI::Text(Coach, EType::Body, Fg, true) ]
						+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 8.f, 0.f, 0.f)
						[ SailUI::Text(TEXT("Rule of the road: starboard tack has right of way over port; the windward boat keeps clear."), EType::Small, Muted, true) ])
				]
			]
		];
	E.Focus = First;
	E.Footer = PromptBar({ Prompt(TEXT("Enter"), TEXT("A"), TEXT("Select")), Prompt(TEXT("Esc"), TEXT("B"), TEXT("Resume")) }, FString());
	return E;
}

// ---------------------------------------------------------------- 5.10 Settings

SSailFrontEnd::FEntry SSailFrontEnd::BuildSettings()
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	FEntry E;
	USailingSettings* S = USailingSettings::Get();
	static const TCHAR* Tabs[] = { TEXT("Graphics"), TEXT("Display"), TEXT("Audio"), TEXT("Gameplay"), TEXT("Accessibility") };
	TSharedRef<SHorizontalBox> TabRow = SNew(SHorizontalBox);
	// Bean's UI feedback (Oct 27): the pills and the Q and E keycaps are buttons too (the mouse), beside Q/E and LB/RB.
	TabRow->AddSlot().AutoWidth().VAlign(VAlign_Center).Padding(0.f, 0.f, 12.f, 0.f)
	[
		SNew(SSailButton).Look(EButtonLook::MenuItem).Padding(FMargin(6.f, 2.f)).OnClicked_Lambda([this]() { SetSettingsTab(SettingsTab + 4); })[ KeyCap(TEXT("Q"), TEXT("LB")) ]
	];
	for (int32 I = 0; I < UE_ARRAY_COUNT(Tabs); ++I)
	{
		TabRow->AddSlot().AutoWidth().Padding(6.f, 0.f)
		[
			SNew(SSailButton).Look(EButtonLook::Chip).IsSelected(I == SettingsTab).Padding(FMargin(14.f, 5.f)).OnClicked_Lambda([this, I]() { SetSettingsTab(I); })
			[ SailUI::Text(Tabs[I], EType::Label, I == SettingsTab ? Ink : Fg) ]
		];
	}
	TabRow->AddSlot().AutoWidth().VAlign(VAlign_Center).Padding(12.f, 0.f, 0.f, 0.f)
	[
		SNew(SSailButton).Look(EButtonLook::MenuItem).Padding(FMargin(6.f, 2.f)).OnClicked_Lambda([this]() { SetSettingsTab(SettingsTab + 1); })[ KeyCap(TEXT("E"), TEXT("RB")) ]
	];
	TSharedRef<SVerticalBox> Rows = SNew(SVerticalBox);
	FString Help;
	auto Add = [&](TSharedRef<SWidget> W) { Rows->AddSlot().AutoHeight().Padding(0.f, 0.f, 0.f, 10.f)[ W ]; if (!E.Focus.IsValid()) E.Focus = W; };
	auto Section = [&](const TCHAR* Name) { Rows->AddSlot().AutoHeight().Padding(0.f, 8.f, 0.f, 8.f)[ SailUI::Text(Name, EType::Eyebrow, Accent) ]; };
	// Picks an option from a list of values (the first that matches, else the first).
	auto IndexOf = [](const TArray<int32>& Values, int32 V) { const int32 I = Values.IndexOfByKey(V); return I == INDEX_NONE ? 0 : I; };
	ASailingGameMode* GM = Player.IsValid() ? Player->GetWorld()->GetAuthGameMode<ASailingGameMode>() : nullptr;
	// Text size rebuilds the screen so the change shows at once.
	auto Rebuild = [this]() { Stack.Last() = Build(ESailScreen::Settings); Show(Stack.Last(), true); };
	switch (SettingsTab)
	{
	case 0:
	{
		// The rows are shared with the gallery's Graphics & view card (SailGraphicsRows), so the two can't drift.
		Add(SailGraphicsRows::Quality(GM));
		Add(SailGraphicsRows::AntiAliasing(GM));
		auto Detail = [&](const TCHAR* Label, int32 USailingSettings::* Field, const TCHAR* Note) { Add(SailGraphicsRows::Detail(GM, Label, Field, Note)); };
		Section(TEXT("Detail"));
		Detail(TEXT("Shadows"), &USailingSettings::ShadowQuality, TEXT("Shadow resolution and distance."));
		Detail(TEXT("Lighting"), &USailingSettings::LightingQuality, TEXT("Lumen's bounced light: the shade inside crowns and under hulls."));
		Detail(TEXT("Reflections"), &USailingSettings::ReflectionQuality, TEXT(""));
		Detail(TEXT("Clouds"), &USailingSettings::CloudQuality, TEXT("Samples through the clouds: the costliest part of the sky."));
		Detail(TEXT("Water"), &USailingSettings::WaterQuality, TEXT("Low keeps the simple water; Medium and up the full sea."));
		Detail(TEXT("Foliage"), &USailingSettings::FoliageQuality, TEXT("How many of the shore's trees are drawn."));
		Detail(TEXT("View distance"), &USailingSettings::ViewDistanceQuality, TEXT(""));
		Add(SailGraphicsRows::MotionBlur(GM));
		Section(TEXT("Rendering"));
		Add(SailGraphicsRows::RenderScale(GM));
		static const TArray<int32> Caps = { 30, 45, 60, 120, 0 };
		Add(SNew(SSailChoice).Label(TEXT("Frame rate cap")).Options({ TEXT("30"), TEXT("45"), TEXT("60"), TEXT("120"), TEXT("Uncapped") })
			.Index_Lambda([S, IndexOf]() { return IndexOf(Caps, S->FrameCap); })
			.OnChanged_Lambda([S](int32 I) { S->FrameCap = Caps[I]; S->Save(); S->ApplyDisplay(); }));
		Add(SNew(SSailChoice).Label(TEXT("Look")).Options({ TEXT("Natural"), TEXT("Cinematic") })
			.Index_Lambda([S]() { return S->bCinematicLook ? 1 : 0; })
			.OnChanged_Lambda([S](int32 I) { S->bCinematicLook = I == 1; S->Save(); })
			.Note(TEXT("Cinematic: a photographic grade (warm highlights, cool shadows), wider bloom and sun glitter. Photo mode always uses it.")));
		Help = TEXT("Quality is a preset: choosing a tier sets every row on Auto to that tier's own. Change a row to override it.\n\n"
			"Measured on the packaged build, slowest view (docs/graphics-3/bench.csv): Medium 71.6 fps, High 45.3 fps on the M5 Pro. "
			"Ultra: full hardware Lumen, strand hair, full-res clouds, no resolution governor (RTX 4090 PC).\n\nRender scale draws the world "
			"at a share of the screen's resolution and upscales it; a fixed scale turns High's governor off.");
		break;
	}
	case 1:
	{
		UGameUserSettings* G = GEngine ? GEngine->GetGameUserSettings() : nullptr;
		Add(SNew(SSailChoice).Label(TEXT("Window")).Options({ TEXT("Windowed"), TEXT("Borderless"), TEXT("Fullscreen") })
			.Index_Lambda([G]()
			{
				// The window as it is (a -windowed run ignores the saved mode).
				const TSharedPtr<SWindow> Window = GEngine && GEngine->GameViewport ? GEngine->GameViewport->GetWindow() : nullptr;
				const EWindowMode::Type M = Window.IsValid() ? Window->GetWindowMode() : (G ? G->GetFullscreenMode() : EWindowMode::Windowed);
				return M == EWindowMode::Windowed ? 0 : (M == EWindowMode::WindowedFullscreen ? 1 : 2);
			})
			.OnChanged_Lambda([G](int32 I)
			{
				if (!G) return;
				G->SetFullscreenMode(I == 0 ? EWindowMode::Windowed : (I == 1 ? EWindowMode::WindowedFullscreen : EWindowMode::Fullscreen));
				G->ApplyResolutionSettings(false);
				G->SaveSettings();
			}));
		// Bean's playtest: the screen's own resolutions (the monitor's list, largest first), not only the render scale.
		TArray<FIntPoint> Modes;
		UKismetSystemLibrary::GetSupportedFullscreenResolutions(Modes);
		Modes.Sort([](const FIntPoint& A, const FIntPoint& B) { return A.X * A.Y > B.X * B.Y; });
		if (G && !Modes.Contains(G->GetScreenResolution())) Modes.Insert(G->GetScreenResolution(), 0);
		if (Modes.Num() > 0)
		{
			TArray<FString> Names;
			for (const FIntPoint& M : Modes) Names.Add(FString::Printf(TEXT("%d x %d"), M.X, M.Y));
			Add(SNew(SSailChoice).Label(TEXT("Resolution")).Options(Names)
				.Index_Lambda([G, Modes]() { return G ? FMath::Max(Modes.IndexOfByKey(G->GetScreenResolution()), 0) : 0; })
				.OnChanged_Lambda([G, Modes](int32 I)
				{
					if (!G || !Modes.IsValidIndex(I)) return;
					G->SetScreenResolution(Modes[I]);
					G->ApplyResolutionSettings(false);
					G->SaveSettings();
				})
				.Note(TEXT("Borderless takes the desktop's; Windowed and Fullscreen use this.")));
		}
		Add(SNew(SSailChoice).Label(TEXT("V-sync")).Options({ TEXT("Off"), TEXT("On") })
			.Index_Lambda([S]() { return S->bVSync ? 1 : 0; })
			.OnChanged_Lambda([S](int32 I) { S->bVSync = I == 1; S->Save(); S->ApplyDisplay(); })
			.Note(TEXT("On: no tearing, the frame rate held to the display's refresh.")));
		Add(SNew(SSailSlider).Label(TEXT("Field of view")).Min(60.f).Max(120.f).Step(5.f)
			.Value_Lambda([S]() { return S->FieldOfView > 0 ? float(S->FieldOfView) : 90.f; })
			.ValueText_Lambda([S]() { return FString::Printf(TEXT("%d°"), S->FieldOfView > 0 ? S->FieldOfView : 90); })
			.OnChanged_Lambda([S](float V) { S->FieldOfView = FMath::RoundToInt32(V) == 90 ? 0 : FMath::RoundToInt32(V); S->Save(); }));
		Add(SNew(SSailSlider).Label(TEXT("Brightness")).Min(50.f).Max(150.f).Step(5.f)
			.Value_Lambda([S]() { return float(S->Brightness); })
			.ValueText_Lambda([S]() { return FString::Printf(TEXT("%d%%"), S->Brightness); })
			.OnChanged_Lambda([S](float V) { S->Brightness = FMath::RoundToInt32(V); S->Save(); }));
		Add(SNew(SSailChoice).Label(TEXT("HUD")).Options({ TEXT("Full"), TEXT("Minimal"), TEXT("Off") })
			.Index_Lambda([S]() { return S->bShowHud ? FMath::Clamp(SSailHud::Mode, 0, 2) : 2; })
			.OnChanged_Lambda([S](int32 I) { S->bShowHud = true; SSailHud::Mode = I; S->Save(); })
			.Note(TEXT("H cycles it while sailing. Off keeps the toasts (aground, capsized) for photos and video.")));
		static const TArray<int32> Sizes = { 85, 100, 115, 130 };
		Add(SNew(SSailChoice).Label(TEXT("HUD size")).Options({ TEXT("85%"), TEXT("100%"), TEXT("115%"), TEXT("130%") })
			.Index_Lambda([S, IndexOf]() { return IndexOf(Sizes, S->HudScale); })
			.OnChanged_Lambda([S](int32 I) { S->HudScale = Sizes[I]; S->Save(); }));
		Help = TEXT("The window choice applies at once. The HUD scales around each corner, so nothing moves into the middle of the view.");
		break;
	}
	case 2:
		Add(SNew(SSailSlider).Label(TEXT("Master volume")).Min(0.f).Max(100.f).Step(5.f).Value_Lambda([S]() { return S->Volume * 100.f; })
			.ValueText_Lambda([S]() { return FString::Printf(TEXT("%.0f"), S->Volume * 100.f); }).OnChanged_Lambda([S](float V) { S->Volume = V / 100.f; S->Save(); }));
		// "Larus atricilla" is CC BY 3.0: the game must credit it (docs/licences, CREDITS.md).
		Help = TEXT("Every sound is synthesised from the wind, water and boat, with a few recorded samples from Wikimedia Commons: "
			"\"Larus atricilla\" by Tony Phillips (CC BY 3.0); \"Gull 1\" by avphillips and \"Rain on a veranda\" by ezwa (public domain).");
		break;
	case 3:
		Section(TEXT("Sailing"));
		Add(SNew(SSailChoice).Label(TEXT("Difficulty")).Options({ TEXT("Easy sailing"), TEXT("Realistic") }).Index_Lambda([S]() { return S->Difficulty == ESailingDifficulty::Easy ? 0 : 1; })
			.OnChanged_Lambda([S](int32 I) { S->Difficulty = I == 0 ? ESailingDifficulty::Easy : ESailingDifficulty::Realistic; S->Save(); }));
		Add(SNew(SSailChoice).Label(TEXT("Learning mode")).Options({ TEXT("On"), TEXT("Off") }).Index_Lambda([S]() { return S->bLearningMode ? 0 : 1; })
			.OnChanged_Lambda([S](int32 I) { S->bLearningMode = I == 0; S->Save(); }));
		Add(SNew(SSailChoice).Label(TEXT("Trim assist")).Options({ TEXT("On"), TEXT("Off") }).Index_Lambda([S]() { return S->bTrimAssist ? 0 : 1; })
			.OnChanged_Lambda([S](int32 I) { S->bTrimAssist = I == 0; S->Save(); }));
		Add(SNew(SSailChoice).Label(TEXT("Controls")).Options({ TEXT("Simple"), TEXT("Full") }).Index_Lambda([S]() { return S->ControlLayout == ESailingControlLayout::Simple ? 0 : 1; })
			.OnChanged_Lambda([S](int32 I) { S->ControlLayout = I == 0 ? ESailingControlLayout::Simple : ESailingControlLayout::Full; S->Save(); })
			.Note(TEXT("Easy always uses Simple: tiller, mainsheet, jib sheet and hiking; the crew handles the rest.")));
		Section(TEXT("Mode"));
		Add(SNew(SSailChoice).Label(TEXT("Mode")).Options({ TEXT("Career"), TEXT("Free Sail") }).Index_Lambda([]() { return SailCareer::IsFreeSail() ? 1 : 0; })
			.OnChanged_Lambda([S](int32 I) { S->bFreeSail = I == 1; S->Save(); })
			.Note(TEXT("Free Sail opens every world, boat and mode and earns no medals. The title screen has the same switch.")));
		Section(TEXT("Units"));
		Add(SNew(SSailChoice).Label(TEXT("Speed")).Options({ TEXT("Knots"), TEXT("mph"), TEXT("km/h") }).Index_Lambda([S]() { return S->SpeedUnits; })
			.OnChanged_Lambda([S](int32 I) { S->SpeedUnits = I; S->Save(); }));
		Add(SNew(SSailChoice).Label(TEXT("Depth")).Options({ TEXT("Feet"), TEXT("Metres"), TEXT("Fathoms") }).Index_Lambda([S]() { return S->DepthUnits; })
			.OnChanged_Lambda([S](int32 I) { S->DepthUnits = I; S->Save(); }));
		Add(SNew(SSailChoice).Label(TEXT("Headings")).Options({ TEXT("Magnetic"), TEXT("True") }).Index_Lambda([S]() { return S->bHeadingsTrue ? 1 : 0; })
			.OnChanged_Lambda([S](int32 I) { S->bHeadingsTrue = I == 1; S->Save(); })
			.Note(TEXT("Galveston applies 1°28′ E. The lake's bake has no variation, so it reads true there.")));
		Section(TEXT("Sessions"));
		Add(SNew(SSailChoice).Label(TEXT("Start when loaded")).Options({ TEXT("Off"), TEXT("On") }).Index_Lambda([S]() { return S->bAutoStart ? 1 : 0; })
			.OnChanged_Lambda([S](int32 I) { S->bAutoStart = I == 1; S->Save(); }));
		Add(SNew(SSailChoice).Label(TEXT("Pause when unfocused")).Options({ TEXT("Off"), TEXT("On") }).Index_Lambda([S]() { return S->bPauseOnFocusLoss ? 1 : 0; })
			.OnChanged_Lambda([S](int32 I) { S->bPauseOnFocusLoss = I == 1; S->Save(); S->ApplyDisplay(); }));
		Section(TEXT("Privacy"));
		Add(SNew(SSailChoice).Label(TEXT("Send crash reports")).Options({ TEXT("Off"), TEXT("On") }).Index_Lambda([S]() { return S->bSendCrashReports ? 1 : 0; })
			.OnChanged_Lambda([S](int32 I) { S->bSendCrashReports = I == 1; S->Save(); S->ApplyCrashReports(); })
			.Note(TEXT("When the game crashes, send the crash, the game's log and where you were sailing to the developer. No name, account or screenshot.")));
		Help = TEXT("Learning mode explains what the boat is doing; Game mode keeps score. The physics is the same in both.\n\n"
			"Off, Start when loaded holds the loading screen until you press Enter, so the first frame you see is smooth.");
		break;
	default:
	{
		static const TArray<int32> Texts = { 100, 115, 130, 150 };
		Add(SNew(SSailChoice).Label(TEXT("Text size")).Options({ TEXT("100%"), TEXT("115%"), TEXT("130%"), TEXT("150%") })
			.Index_Lambda([S, IndexOf]() { return IndexOf(Texts, S->TextScale); })
			.OnChanged_Lambda([S, Rebuild](int32 I) { S->TextScale = Texts[I]; S->Save(); Rebuild(); })
			.Note(TEXT("Body text, notes and instrument labels. The HUD takes it at the next session.")));
		Add(SNew(SSailChoice).Label(TEXT("Port and starboard colours")).Options({ TEXT("Red and green") }).Index(0)
			.Note(TEXT("The HUD pairs every side colour with a letter (P and S) or a word, so it never relies on colour alone.")));
		Help = TEXT("Every screen works with the keyboard, a controller or the mouse; the prompts follow whichever you used last.");
		break;
	}
	}
	// Every tab ends with the credits (fonts, sounds, data and the engine).
	Rows->AddSlot().AutoHeight().Padding(0.f, 18.f, 0.f, 0.f)
	[
		SNew(SSailButton).Look(EButtonLook::Secondary).Padding(FMargin(14.f, 6.f)).OnClicked_Lambda([this]() { Push(ESailScreen::Credits); })
		[ SailUI::Text(TEXT("Credits and licences"), EType::Ui, Fg) ]
	];
	E.Content = SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight()[ Header(TEXT("Settings"), Tabs[SettingsTab], 0) ]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 16.f, 0.f, 20.f)[ TabRow ]
		+ SVerticalBox::Slot().FillHeight(1.f).Padding(0.f, 0.f, 0.f, 90.f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().FillWidth(0.62f).Padding(0.f, 0.f, 20.f, 0.f)[ SNew(SScrollBox) + SScrollBox::Slot()[ Rows ] ]
			+ SHorizontalBox::Slot().FillWidth(0.38f).VAlign(VAlign_Top)[ PanelBox(SailUI::Text(Help, EType::Body, Muted, true)) ]
		];
	E.Footer = PromptBar({ Prompt(TEXT("← →"), TEXT("← →"), TEXT("Change")), Prompt(TEXT("Q / E"), TEXT("LB / RB"), TEXT("Tab")),
		Prompt(TEXT("Esc"), TEXT("B"), TEXT("Back")) }, TEXT("Changes apply at once and are saved"));
	return E;
}

// ---------------------------------------------------------------- 5.11 Controls

SSailFrontEnd::FEntry SSailFrontEnd::BuildControls()
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	FEntry E;
	ASailboatPawn* P = Pawn();
	TSharedRef<SVerticalBox> Rows = SNew(SVerticalBox);
	if (P)
	{
		P->UIBuildKeyRows();
		const TArray<ASailboatPawn::FKeyRow>& Keys = P->GetKeyRows();
		const bool bPadFirst = UsingGamepad();
		Rows->AddSlot().AutoHeight().Padding(14.f, 0.f, 14.f, 8.f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().FillWidth(1.f)[ SailUI::Text(TEXT("Command"), EType::Label, Muted) ]
			+ SHorizontalBox::Slot().AutoWidth()[ SNew(SBox).WidthOverride(150.f)[ SailUI::Text(TEXT("Keyboard"), EType::Label, Muted) ] ]
			+ SHorizontalBox::Slot().AutoWidth()[ SNew(SBox).WidthOverride(170.f)[ SailUI::Text(TEXT("Controller"), EType::Label, Muted) ] ]
		];
		for (int32 I = 0; I < Keys.Num(); ++I)
		{
			const bool bListenKey = ListeningRow == I && !bListeningPad, bListenPad = ListeningRow == I && bListeningPad;
			// The gamepad column: its button, else the stick or trigger that drives it (fixed, dimmed), else a dash.
			const ASailboatPawn::FKeyRow& Row = Keys[I];
			const bool bAxis = !Row.PadKey.IsValid() && Row.PadAxis.IsValid();
			const FString Pad = bListenPad ? FString(TEXT("Press a button…")) : Row.PadKey.IsValid() ? SailingBindings::PadLabel(Row.PadKey)
				: bAxis ? SailingBindings::PadLabel(Row.PadAxis) + TEXT(" (fixed)") : FString(TEXT("–"));
			TSharedRef<SSailButton> B = SNew(SSailButton).Look(EButtonLook::Secondary).Padding(FMargin(14.f, 6.f))
				.OnClicked_Lambda([this, I]() { ListenControls(I, false); })
				.OnFocused_Lambda([this, I]() { FocusedControlRow = I; })
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().FillWidth(1.f)[ SailUI::Text(Row.Label, EType::Ui, Fg) ]
				+ SHorizontalBox::Slot().AutoWidth()[ SNew(SBox).WidthOverride(150.f)[ SailUI::Text(bListenKey ? FString(TEXT("Press a key…")) : Row.Key.GetDisplayName().ToString(), EType::Value, bListenKey ? Accent : (bPadFirst ? Muted : Fg)) ] ]
				+ SHorizontalBox::Slot().AutoWidth()[ SNew(SBox).WidthOverride(170.f)[ SailUI::Text(Pad, EType::Value, bListenPad ? Accent : bAxis || !Row.PadKey.IsValid() ? Dim : (bPadFirst ? Fg : Muted)) ] ]
			];
			Rows->AddSlot().AutoHeight().Padding(0.f, 0.f, 0.f, 6.f)[ B ];
			if (!E.Focus.IsValid() || I == ListeningRow || (ListeningRow < 0 && I == FocusedControlRow)) E.Focus = B;
		}
		Rows->AddSlot().AutoHeight().Padding(0.f, 10.f, 0.f, 0.f)
		[
			SNew(SSailButton).Look(EButtonLook::Secondary).Padding(FMargin(14.f, 6.f))
			.OnClicked_Lambda([this]()
			{
				if (ASailboatPawn* RP = Pawn()) { RP->ResetKeys(); ControlsMessage = RP->GetKeysMessage(); }
				ListeningRow = -1;
				Stack.Last() = Build(ESailScreen::Controls);
				Show(Stack.Last(), true);
			})
			.OnFocused_Lambda([this, N = Keys.Num()]() { FocusedControlRow = N; })
			[ SailUI::Text(TEXT("Restore the defaults (keyboard and controller)"), EType::Ui, Fg) ]
		];
	}
	E.Content = SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight()[ Header(TEXT("Controls"), TEXT("Keys and buttons"), 0) ]
		+ SVerticalBox::Slot().FillHeight(1.f).Padding(0.f, 24.f, 0.f, 90.f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().FillWidth(0.66f).Padding(0.f, 0.f, 20.f, 0.f)[ SNew(SScrollBox) + SScrollBox::Slot()[ Rows ] ]
			+ SHorizontalBox::Slot().FillWidth(0.34f)
			[
				PanelBox(SNew(SVerticalBox)
					+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(TEXT("Select a command, then press the new key (Enter or A) or controller button (Tab or Y). A key or button that another command used swaps over, so nothing is left without one."), EType::Body, Muted, true) ]
					+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 12.f, 0.f, 0.f)[ SailUI::Text(TEXT("Sticks and triggers stay on their axes (steering, the mainsheet, the camera) and can't be rebound. B cancels a listen, so B itself is reached by a swap or the defaults."), EType::Body, Muted, true) ]
					+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 12.f, 0.f, 0.f)[ SailUI::Text(ControlsMessage, EType::Body, Accent, true) ]
					+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 12.f, 0.f, 0.f)[ SailUI::Text(TEXT("Bindings are saved in Input.ini, so the Mac and the PC can differ."), EType::Small, Dim, true) ])
			]
		];
	E.Footer = PromptBar({ Prompt(TEXT("Enter"), TEXT("A"), TEXT("Rebind key")), Prompt(TEXT("Tab"), TEXT("Y"), TEXT("Rebind button")), Prompt(TEXT("Esc"), TEXT("B"), TEXT("Back")) }, FString());
	return E;
}

// ---------------------------------------------------------------- Credits

SSailFrontEnd::FEntry SSailFrontEnd::BuildCredits()
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	FEntry E;
	const TArray<SailCatalog::FCreditLine> Lines = SailCatalog::Credits();
	FString Title = TEXT("Credits and licences");
	TSharedRef<SVerticalBox> Rows = SNew(SVerticalBox);
	for (const SailCatalog::FCreditLine& L : Lines)
	{
		switch (L.Kind)
		{
		case SailCatalog::ECreditKind::Notice:
			Rows->AddSlot().AutoHeight().Padding(0.f, 0.f, 0.f, 18.f)[ SailUI::Text(L.Text, EType::CardTitleS, Fg, true) ];
			break;
		case SailCatalog::ECreditKind::Heading1:
			Title = L.Text;   // the page's own title heads the screen
			break;
		case SailCatalog::ECreditKind::Heading2:
			Rows->AddSlot().AutoHeight().Padding(0.f, 22.f, 0.f, 8.f)[ SailUI::Text(L.Text, EType::CardTitleS, Accent, true) ];
			break;
		case SailCatalog::ECreditKind::Heading3:
			Rows->AddSlot().AutoHeight().Padding(0.f, 14.f, 0.f, 6.f)[ SailUI::Text(L.Text, EType::Eyebrow, Accent, true) ];
			break;
		case SailCatalog::ECreditKind::Bullet:
			Rows->AddSlot().AutoHeight().Padding(0.f, 0.f, 0.f, 6.f)
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().AutoWidth().Padding(4.f, 0.f, 12.f, 0.f)[ SailUI::Text(TEXT("\u2022"), EType::Body, Dim) ]
				+ SHorizontalBox::Slot().FillWidth(1.f)[ SailUI::Text(L.Text, EType::Body, Muted, true) ]
			];
			break;
		default:
			Rows->AddSlot().AutoHeight().Padding(0.f, 0.f, 0.f, 10.f)[ SailUI::Text(L.Text, EType::Body, Muted, true) ];
			break;
		}
	}
	Rows->AddSlot().AutoHeight().Padding(0.f, 24.f, 0.f, 0.f)[ SailUI::Text(TEXT("From CREDITS.md, shipped with the game."), EType::Small, Dim, true) ];
	CreditsScroll = SNew(SScrollBox).ScrollBarAlwaysVisible(true) + SScrollBox::Slot().Padding(0.f, 0.f, 18.f, 0.f)[ Rows ];
	E.Content = SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight()[ Header(TEXT("Credits"), Title, 0) ]
		+ SVerticalBox::Slot().FillHeight(1.f).Padding(0.f, 24.f, 0.f, 90.f)
		[
			// A reading measure, not the full width of a wide screen.
			SNew(SHorizontalBox) + SHorizontalBox::Slot().FillWidth(1.f).MaxWidth(1180.f)[ PanelBox(CreditsScroll.ToSharedRef(), FMargin(26.f, 22.f)) ]
		];
	// No focus target: the front end itself takes the keys and scrolls.
	E.Footer = PromptBar({ Prompt(TEXT("\u2191 \u2193"), TEXT("\u2191 \u2193"), TEXT("Scroll")), Prompt(TEXT("PgUp / PgDn"), TEXT("LB / RB"), TEXT("Page")),
		Prompt(TEXT("Esc"), TEXT("B"), TEXT("Back")) }, FString());
	return E;
}

// ---------------------------------------------------------------- Graphics G7: drill briefing and quiz

SSailFrontEnd::FEntry SSailFrontEnd::BuildBriefing()
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	FEntry E;
	const ASailboatPawn* P = Pawn();
	const FDrillBriefing* B = P ? FLearningContent::Get().Briefing(P->GetDrill().GetDrill()) : nullptr;
	TSharedRef<SSailButton> Go = ActionButton(TEXT("Start the drill"), FSimpleDelegate::CreateLambda([this]() { Close(); }));
	if (!B)
	{
		E.Content = SNew(SBox).VAlign(VAlign_Center)[ Go ];
		E.Focus = Go;
		return E;
	}
	auto Para = [](const FString& Label, const FString& Text, const FLinearColor& Color) -> TSharedRef<SWidget>
	{
		return SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(Label, EType::Eyebrow, Accent) ]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 4.f, 0.f, 0.f)[ SailUI::Text(Text, EType::Body, Color, true) ];
	};
	// Left: what and why, the setup and the crew's calls.
	TSharedRef<SVerticalBox> Calls = SNew(SVerticalBox);
	for (const FDrillBriefing::FCommand& C : B->Commands)
	{
		Calls->AddSlot().AutoHeight().Padding(0.f, 4.f)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(C.Reply.IsEmpty() ? FString::Printf(TEXT("“%s”"), *C.Call) : FString::Printf(TEXT("“%s”  →  “%s”"), *C.Call, *C.Reply), EType::Value, Fg, true) ]
			+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(C.Meaning, EType::Small, Muted, true) ]
		];
	}
	TSharedRef<SVerticalBox> Left = SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(FString::Printf(TEXT("Drill briefing · ASA 101 · %s"), *B->AsaSkill), EType::Eyebrow, Accent) ]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 4.f, 0.f, 14.f)[ SailUI::Text(B->Name, B->Name.Len() > 18 ? EType::CardTitle : EType::ScreenTitle, Fg, true) ]
		+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(B->Goal, EType::Value, Fg, true) ]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 8.f, 0.f, 0.f)[ SailUI::Text(B->Why, EType::Body, Muted, true) ]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 18.f, 0.f, 0.f)[ Para(TEXT("Setup"), B->Setup, Fg) ];
	if (B->Commands.Num()) Left->AddSlot().AutoHeight().Padding(0.f, 18.f, 0.f, 0.f)
	[
		SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(TEXT("Calls"), EType::Eyebrow, Accent) ]
		+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 2.f, 0.f, 0.f)[ Calls ]
	];
	if (!B->LakeNotes.IsEmpty()) Left->AddSlot().AutoHeight().Padding(0.f, 18.f, 0.f, 0.f)[ Para(TEXT("On the lake"), B->LakeNotes, Muted) ];
	Left->AddSlot().AutoHeight().Padding(0.f, 26.f, 0.f, 0.f)[ SNew(SBox).WidthOverride(320.f)[ Go ] ];

	// Right: the steps with the coach's notes, what good looks like, the usual mistakes.
	TSharedRef<SVerticalBox> Right = SNew(SVerticalBox);
	Right->AddSlot().AutoHeight()[ SailUI::Text(TEXT("Steps"), EType::Eyebrow, Accent) ];
	for (int32 I = 0; I < B->Steps.Num(); ++I)
	{
		Right->AddSlot().AutoHeight().Padding(0.f, 8.f, 0.f, 0.f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 12.f, 0.f)[ SNew(SBox).WidthOverride(22.f)[ SailUI::Text(FString::FromInt(I + 1), EType::Value, Accent) ] ]
			+ SHorizontalBox::Slot().FillWidth(1.f)
			[
				SNew(SVerticalBox)
				+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(B->StepText(I), EType::Ui, Fg, true) ]
				+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 2.f, 0.f, 0.f)[ SailUI::Text(FLearningContent::ResolveKeys(B->Steps[I].Coach), EType::Small, Muted, true) ]
			]
		];
	}
	if (B->Good.Num())
	{
		Right->AddSlot().AutoHeight().Padding(0.f, 18.f, 0.f, 0.f)[ SailUI::Text(TEXT("What good looks like"), EType::Eyebrow, Starboard) ];
		for (const FString& G : B->Good) Right->AddSlot().AutoHeight().Padding(0.f, 4.f, 0.f, 0.f)[ SailUI::Text(TEXT("•  ") + G, EType::Small, Fg, true) ];
	}
	if (B->Mistakes.Num())
	{
		Right->AddSlot().AutoHeight().Padding(0.f, 18.f, 0.f, 0.f)[ SailUI::Text(TEXT("Common mistakes"), EType::Eyebrow, Warn) ];
		for (const TPair<FString, FString>& M : B->Mistakes)
		{
			Right->AddSlot().AutoHeight().Padding(0.f, 5.f, 0.f, 0.f)
			[
				SNew(SVerticalBox)
				+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(M.Key, EType::Small, Fg, true) ]
				+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(TEXT("Fix: ") + M.Value, EType::Small, Muted, true) ]
			];
		}
	}
	E.Content = SNew(SHorizontalBox)
		+ SHorizontalBox::Slot().FillWidth(0.46f).Padding(0.f, 0.f, 40.f, 0.f)[ SNew(SScrollBox) + SScrollBox::Slot()[ Left ] ]
		+ SHorizontalBox::Slot().FillWidth(0.54f).Padding(0.f, 0.f, 0.f, 90.f)[ PanelBox(SNew(SScrollBox) + SScrollBox::Slot()[ Right ], FMargin(26.f, 22.f)) ];
	E.Focus = Go;
	E.Footer = PromptBar({ Prompt(TEXT("Enter"), TEXT("A"), TEXT("Start the drill")), Prompt(TEXT("Esc"), TEXT("B"), TEXT("Skip")) }, TEXT("The game is paused while you read"));
	return E;
}

void SSailFrontEnd::StartQuiz()
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	QuizLessonId.Reset();
	QuizCareerLine.Reset();
	FRandomStream Rng{ int32(FPlatformTime::Cycles()) };
	if (!CheckrideTierId.IsEmpty())
	{
		// Career 1: a checkride's written quiz, from the Career screen.
		const FCareerContent& Content = FCareerContent::Get();
		const FCareerTier* T = Content.Tier(CheckrideTierId);
		Quiz = T ? Content.MakeCheckrideQuiz(*T, FLearningContent::Get(), Rng) : TArray<FQuizQuestion>();
		QuizIndex = QuizRight = 0;
		QuizChosen = -1;
		QuizDrillName = T ? T->Checkride.Title : FString();
		QuizDebrief = T ? FString::Printf(TEXT("The written part of the checkride: %d questions across the tier's %d lessons. %d right passes."), Quiz.Num(),
			T->Checkride.Lessons.Num(), FMath::CeilToInt32(T->Checkride.Quiz.Pass * Quiz.Num() - 1e-6)) : FString();
		return;
	}
	const ASailboatPawn* P = Pawn();
	const ESailingDrill Drill = P ? P->GetDrill().GetDrill() : ESailingDrill::None;
	Quiz = FLearningContent::Get().MakeQuiz(Drill, Rng);
	QuizIndex = QuizRight = 0;
	QuizChosen = -1;
	QuizDrillName = DrillName(Drill);
	QuizDebrief.Reset();
	if (P)
	{
		const FDrillRunner& D = P->GetDrill();
		FString Outcome = D.GetOutcome();
		if (Outcome.IsEmpty() && FDrillRunner::Outcomes(Drill).Num()) Outcome = FDrillRunner::Outcomes(Drill)[0];   // stills before the drill ends
		QuizDebrief = FLearningContent::Get().Debrief(Drill, Outcome, D.GetElapsed(), P->GetMaxContactKnots());
		// Career 1: the lesson this drill counted for, and its medal; the quiz closes it.
		const FCareerProgress::FAward& A = P->GetCareerAward();
		if (const FCareerLesson* L = A.IsValid() ? FCareerContent::Get().Lesson(A.LessonId) : nullptr)
		{
			QuizLessonId = L->Id;
			const int32 Sec = FMath::RoundToInt32(A.Seconds);
			QuizDebrief += FString::Printf(TEXT("%sLesson: %s · %s medal in %d:%02d%s."), QuizDebrief.IsEmpty() ? TEXT("") : TEXT("\n\n"), *L->Title,
				*FCareerContent::MedalName(A.Medal), Sec / 60, Sec % 60, A.bNewBest && A.Medal != ECareerMedal::None ? TEXT(", a new best") : TEXT(""));
			// Easy mode: honest grading (career.json's easy_max_medal).
			if (A.bEasyCapped) QuizDebrief += FString::Printf(TEXT(" Sailed on Easy, which earns at most %s: sail it on Realistic for more."),
				*FCareerContent::MedalName(FCareerContent::Get().EasyMaxMedal).ToLower());
		}
		else if (SailCareer::IsFreeSail() && D.IsComplete())
		{
			QuizDebrief += FString::Printf(TEXT("%sFree Sail: no medal. Sail it in Career mode to grade the lesson."), QuizDebrief.IsEmpty() ? TEXT("") : TEXT("\n\n"));
		}
	}
}

SSailFrontEnd::FEntry SSailFrontEnd::BuildQuiz()
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	FEntry E;
	auto Rebuild = [this]() { Stack.Last() = Build(ESailScreen::Quiz); Show(Stack.Last(), true); };
	TSharedRef<SVerticalBox> Box = SNew(SVerticalBox);
	const bool bDone = QuizIndex >= Quiz.Num();
	Box->AddSlot().AutoHeight()[ SailUI::Text(bDone ? FString::Printf(TEXT("Quiz · %s"), *QuizDrillName)
		: FString::Printf(TEXT("Quiz · %s · question %d of %d"), *QuizDrillName, QuizIndex + 1, Quiz.Num()), EType::Eyebrow, Accent) ];
	if (!QuizDebrief.IsEmpty() && (QuizIndex == 0 || bDone))
		Box->AddSlot().AutoHeight().Padding(0.f, 8.f, 0.f, 4.f)[ SailUI::Text(QuizDebrief, EType::Body, Muted, true) ];
	if (bDone)
	{
		const bool bCheckride = !CheckrideTierId.IsEmpty();
		TSharedRef<SSailButton> Done = ActionButton(bCheckride ? TEXT("Back to the career") : TEXT("Back to sailing"), FSimpleDelegate::CreateLambda([this, bCheckride]()
		{
			if (bCheckride) Pop();
			else { Quiz.Reset(); Close(); }
		}));
		Box->AddSlot().AutoHeight().Padding(0.f, 16.f, 0.f, 6.f)[ SailUI::Text(FString::Printf(TEXT("%d of %d right"), QuizRight, Quiz.Num()), EType::ScreenTitle, QuizRight == Quiz.Num() ? Starboard : Fg) ];
		Box->AddSlot().AutoHeight()[ SailUI::Text(QuizRight == Quiz.Num() ? TEXT("All correct. On to the next drill.") : TEXT("The drill panel's coach notes and the briefing cover the ones you missed."), EType::Body, Muted, true) ];
		if (!QuizCareerLine.IsEmpty()) Box->AddSlot().AutoHeight().Padding(0.f, 10.f, 0.f, 0.f)[ SailUI::Text(QuizCareerLine, EType::Body, Accent, true) ];
		Box->AddSlot().AutoHeight().Padding(0.f, 24.f, 0.f, 0.f)[ SNew(SBox).WidthOverride(320.f)[ Done ] ];
		E.Focus = Done;
	}
	else
	{
		const FQuizQuestion& Q = Quiz[QuizIndex];
		const bool bAnswered = QuizChosen >= 0;
		Box->AddSlot().AutoHeight().Padding(0.f, 14.f, 0.f, 16.f)[ SailUI::Text(Q.Question, EType::Value, Fg, true) ];
		TSharedPtr<SWidget> First;
		for (int32 I = 0; I < Q.Options.Num(); ++I)
		{
			const bool bRight = I == Q.Answer, bChosen = I == QuizChosen;
			const FLinearColor Edge = !bAnswered ? FLinearColor::Transparent : (bRight ? Starboard : (bChosen ? Port : FLinearColor::Transparent));
			TSharedRef<SSailButton> Opt = SNew(SSailButton).Look(EButtonLook::Card).Padding(FMargin(16.f, 10.f)).IsEnabled(!bAnswered)
				.OnClicked(FSimpleDelegate::CreateLambda([this, I, Rebuild]()
				{
					if (QuizChosen >= 0 || !Quiz.IsValidIndex(QuizIndex)) return;
					QuizChosen = I;
					if (I == Quiz[QuizIndex].Answer) ++QuizRight;
					Rebuild();
				}))
			[
				SNew(SBorder).BorderImage(Rounded(FLinearColor::Transparent, RadiusButton, Edge, 2.f)).Padding(FMargin(8.f, 4.f))
				[
					SNew(SHorizontalBox)
					+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 14.f, 0.f)[ SailUI::Text(FString::Chr(TCHAR('A' + I)), EType::Value, bAnswered && bRight ? Starboard : Accent) ]
					+ SHorizontalBox::Slot().FillWidth(1.f)[ SailUI::Text(Q.Options[I], EType::Body, bAnswered && !bRight && !bChosen ? Muted : Fg, true) ]
				]
			];
			Box->AddSlot().AutoHeight().Padding(0.f, 4.f)[ Opt ];
			if (!First.IsValid()) First = Opt;
		}
		if (bAnswered)
		{
			const bool bWasRight = QuizChosen == Q.Answer;
			const bool bLast = QuizIndex + 1 >= Quiz.Num();
			TSharedRef<SSailButton> Next = ActionButton(bLast ? TEXT("See the score") : TEXT("Next question"), FSimpleDelegate::CreateLambda([this, Rebuild]()
			{
				++QuizIndex;
				QuizChosen = -1;
				if (QuizIndex >= Quiz.Num())
				{
					if (ASailboatPawn* B = Pawn()) B->AddLogEvent(FString::Printf(TEXT("Quiz after %s: %d of %d"), *QuizDrillName, QuizRight, Quiz.Num()));
					// Career 1: the score goes to the lesson, or to the checkride (which may award the certificate).
					const FCareerContent& Content = FCareerContent::Get();
					if (const FCareerTier* T = Content.Tier(CheckrideTierId))
					{
						const bool bAwarded = SailCareer::RecordCheckrideQuiz(T->Id, QuizRight, Quiz.Num());
						if (bAwarded)
						{
							TArray<FString> Opens;
							for (const FString& Id : T->Unlocks.Tiers) if (const FCareerTier* X = Content.Tier(Id)) Opens.Add(X->Name);
							QuizCareerLine = T->CertificateName + TEXT(" earned.") + (Opens.Num() ? FString::Printf(TEXT(" Open now: %s."), *FString::Join(Opens, TEXT(", "))) : FString());
						}
						else if (T->Checkride.Quiz.Passes(QuizRight, Quiz.Num())) QuizCareerLine = FString::Printf(TEXT("Passed. The %s is already yours."), *T->CertificateName);
						else QuizCareerLine = FString::Printf(TEXT("%d right passes: read the briefings again and retake it from the Career screen."),
							FMath::CeilToInt32(T->Checkride.Quiz.Pass * Quiz.Num() - 1e-6));
					}
					else if (const FCareerLesson* L = Content.Lesson(QuizLessonId))
					{
						const bool bPass = SailCareer::RecordLessonQuiz(L->Id, QuizRight, Quiz.Num());
						QuizCareerLine = bPass ? FString::Printf(TEXT("%s: lesson closed."), *L->Title)
							: FString::Printf(TEXT("%d right closes the lesson: sail the drill again to retake the quiz."), FMath::CeilToInt32(L->QuizPass * Quiz.Num() - 1e-6));
					}
				}
				Rebuild();
			}));
			Box->AddSlot().AutoHeight().Padding(0.f, 14.f, 0.f, 0.f)[ SailUI::Text(bWasRight ? TEXT("Correct") : TEXT("Not quite"), EType::CardTitleS, bWasRight ? Starboard : Port) ];
			Box->AddSlot().AutoHeight().Padding(0.f, 4.f, 0.f, 0.f)[ SailUI::Text(Q.Why, EType::Body, Fg, true) ];
			Box->AddSlot().AutoHeight().Padding(0.f, 18.f, 0.f, 0.f)[ SNew(SBox).WidthOverride(320.f)[ Next ] ];
			E.Focus = Next;
		}
		else
		{
			E.Focus = First;
		}
	}
	E.Content = SNew(SBox).HAlign(HAlign_Center).VAlign(VAlign_Center).Padding(FMargin(0.f, 0.f, 0.f, 80.f))
	[
		SNew(SBox).WidthOverride(940.f)[ PanelBox(Box, FMargin(34.f, 28.f)) ]
	];
	E.Footer = PromptBar({ Prompt(TEXT("Enter"), TEXT("A"), TEXT("Choose")), Prompt(TEXT("Esc"), TEXT("B"), TEXT("Skip the quiz")) }, TEXT("Questions in ASA 101 wording, set on the lake"));
	return E;
}

// ---------------------------------------------------------------- Career

SSailFrontEnd::FEntry SSailFrontEnd::BuildCareer()
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	FEntry E;
	const FCareerContent& Content = FCareerContent::Get();
	const FCareerProgress Career = SailCareer::Progress();
	const FSailSave::FProgress& Prog = Career.Get();
	auto MedalColour = [](ECareerMedal M)
	{
		return M == ECareerMedal::Gold ? Hex(0xE2B84E) : (M == ECareerMedal::Silver ? Hex(0xC4CDD3) : (M == ECareerMedal::Bronze ? Hex(0xC08552) : Dim));
	};
	auto Rebuild = [this]() { Stack.Last() = Build(ESailScreen::Career); Show(Stack.Last(), true); };
	// The tier on show: the one chosen, else the first open tier without its certificate.
	const FCareerTier* Shown = Content.Tier(CareerTierId);
	for (const FCareerTier& T : Content.Tiers)
	{
		if (Shown) break;
		if (Career.IsTierOpen(T.Id) && T.IsReady() && !Career.HasCertificate(T.CertificateId)) Shown = &T;
	}
	if (!Shown && Content.Tiers.Num()) Shown = &Content.Tiers[0];

	// Left: the tiers.
	TSharedRef<SVerticalBox> Tiers = SNew(SVerticalBox);
	for (const FCareerTier& T : Content.Tiers)
	{
		const bool bOpen = Career.IsTierOpen(T.Id), bHeld = Career.HasCertificate(T.CertificateId);
		FString State;
		if (bHeld) State = TEXT("Certificate earned");
		else if (!bOpen)
		{
			const FCareerTier* By = Content.Tiers.FindByPredicate([&T](const FCareerTier& X) { return X.Unlocks.Tiers.Contains(T.Id); });
			State = By ? FString::Printf(TEXT("Earn the %s"), *By->CertificateName) : FString(TEXT("Locked"));
		}
		else if (!T.IsReady()) State = TEXT("Lessons to come");
		else State = FString::Printf(TEXT("%d of %d lessons · %d at silver"), Career.LessonsAtLeast(T, ECareerMedal::Bronze), T.Lessons.Num(), Career.LessonsAtLeast(T, ECareerMedal::Silver));
		const FString Id = T.Id;
		TSharedRef<SSailButton> Card = SNew(SSailButton).Padding(FMargin(16.f, 12.f)).IsSelected_Lambda([Shown, Id]() { return Shown && Shown->Id == Id; })
			.OnClicked_Lambda([this, Id, Rebuild]() { CareerTierId = Id; Rebuild(); })
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().FillWidth(1.f)[ SailUI::Text(T.Name, EType::CardTitleS, bOpen ? Fg : Muted) ]
				+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 24.f, 0.f)[ Pill(bHeld ? TEXT("Certified") : (bOpen ? TEXT("Open") : TEXT("Locked")), bHeld) ]
			]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 4.f, 0.f, 0.f)[ SailUI::Text(State, EType::Small, Muted) ]
		];
		Tiers->AddSlot().AutoHeight().Padding(0.f, 0.f, 0.f, 10.f)[ Card ];
		if (Shown && Shown->Id == T.Id) E.Focus = Card;
	}
	// The logbook's totals under the tiers.
	Tiers->AddSlot().AutoHeight().Padding(0.f, 8.f, 0.f, 0.f)
	[
		PanelBox(SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().FillWidth(1.f)[ Fact(FString::Printf(TEXT("%.1f"), Prog.HoursSailed), TEXT("Hours")) ]
			+ SHorizontalBox::Slot().FillWidth(1.f)[ Fact(FString::Printf(TEXT("%.1f"), Prog.LogbookMiles), TEXT("Miles")) ]
			+ SHorizontalBox::Slot().FillWidth(1.f)[ Fact(FString::Printf(TEXT("%d/%d"), Prog.RacesWon, Prog.RacesSailed), TEXT("Races won")) ], FMargin(16.f, 12.f))
	];

	// Right: the tier's lessons and checkride.
	TSharedRef<SVerticalBox> Detail = SNew(SVerticalBox);
	if (Shown)
	{
		const FCareerTier& T = *Shown;
		const bool bOpen = Career.IsTierOpen(T.Id);
		const int32 WorldIndex = FMath::Max(FSailSave::WorldIndex(T.WorldId), 0);
		TArray<FString> BoatNames;
		for (const FString& B : T.Boats) if (FSailSave::BoatIndex(B) >= 0) BoatNames.Add(SailCatalog::Boat(FSailSave::BoatIndex(B)).Name);
		Detail->AddSlot().AutoHeight()[ SailUI::Text(FString::Printf(TEXT("%s · %s"), *(WorldIndex < 2 ? SailCatalog::World(WorldIndex).Name : FString(TEXT("The Gulf"))),
			BoatNames.Num() ? *FString::Join(BoatNames, TEXT(", ")) : TEXT("boats to come")), EType::Eyebrow, Accent) ];
		Detail->AddSlot().AutoHeight().Padding(0.f, 6.f, 0.f, 4.f)[ SailUI::Text(T.Summary, EType::Body, Fg, true) ];
		if (!T.Learning.IsEmpty()) Detail->AddSlot().AutoHeight().Padding(0.f, 0.f, 0.f, 14.f)[ SailUI::Text(T.Learning, EType::Small, Muted, true) ];
		for (int32 I = 0; I < T.Lessons.Num(); ++I)
		{
			const FCareerLesson& L = T.Lessons[I];
			const FSailSave::FLessonRecord* R = Prog.FindLesson(L.Id);
			const ECareerMedal M = Career.LessonMedal(L.Id);
			// Easy mode: a medal earned on Easy says so ("Easy: bronze").
			const FString MedalText = M == ECareerMedal::None ? FString(TEXT("No medal"))
				: (Career.IsLessonMedalEasy(L.Id) ? FString::Printf(TEXT("Easy: %s"), *FCareerContent::MedalName(M).ToLower()) : FCareerContent::MedalName(M));
			const int32 Sec = R ? FMath::RoundToInt32(R->BestSeconds) : 0;
			const FString QuizText = !R || R->QuizOf == 0 ? FString(TEXT("Quiz to take")) : (R->bQuizPassed ? FString(TEXT("Quiz passed")) : FString::Printf(TEXT("Quiz %d of %d"), R->QuizBest, R->QuizOf));
			const ESailingDrill Drill = L.Drill;
			const FString TierWorld = T.WorldId, TierBoat = T.Boats.Num() ? T.Boats[0] : FString(TEXT("J22"));
			TSharedRef<SSailButton> Row = SNew(SSailButton).Padding(FMargin(14.f, 8.f)).IsEnabled(bOpen)
				.OnClicked_Lambda([this, Drill, TierWorld, TierBoat]()
				{
					// Sail this lesson: its drill, in the tier's world and first boat; the flow goes on from the launch spot.
					Pending = USailSessionSubsystem::MakeDefault();
					Pending.World = FMath::Max(FSailSave::WorldIndex(TierWorld), 0);
					Pending.LaunchSpot = 0;
					Pending.Boat = FMath::Max(FSailSave::BoatIndex(TierBoat), 0);
					Pending.Mode = ESailMode::Drill;
					Pending.DrillIndex = int32(Drill) - 1;
					Push(ESailScreen::Launch);
				})
			[
				SNew(SHorizontalBox)
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0.f, 0.f, 12.f, 0.f)[ SNew(SBox).WidthOverride(22.f)[ SailUI::Text(FString::FromInt(I + 1), EType::Value, Muted) ] ]
				+ SHorizontalBox::Slot().FillWidth(1.f).VAlign(VAlign_Center)[ SailUI::Text(L.Title, EType::Ui, Fg) ]
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(12.f, 0.f)[ SNew(SBox).WidthOverride(110.f)[ SailUI::Text(QuizText, EType::Small, R && R->bQuizPassed ? Starboard : Muted) ] ]
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(12.f, 0.f)[ SNew(SBox).WidthOverride(56.f)[ SailUI::Text(M == ECareerMedal::None ? FString(TEXT("–")) : FString::Printf(TEXT("%d:%02d"), Sec / 60, Sec % 60), EType::Value, Fg) ] ]
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)[ SNew(SBox).WidthOverride(104.f)[ SailUI::Text(MedalText, EType::Label, MedalColour(M)) ] ]
			];
			Detail->AddSlot().AutoHeight().Padding(0.f, 0.f, 0.f, 6.f)[ Row ];
		}
		if (T.Lessons.Num() == 0)
		{
			Detail->AddSlot().AutoHeight().Padding(0.f, 6.f)[ PanelBox(SailUI::Text(T.Notes.IsEmpty() ? FString(TEXT("Lessons for this tier are still being written.")) : T.Notes, EType::Body, Muted, true), FMargin(16.f, 12.f)) ];
		}
		// The checkride and the certificate.
		FString Why;
		const bool bReady = Career.IsCheckrideReady(T.Id, &Why);
		const bool bHeld = Career.HasCertificate(T.CertificateId);
		const FSailSave::FCertificateRecord* Cert = Prog.Certificates.FindByPredicate([&T](const FSailSave::FCertificateRecord& C) { return C.Id == T.CertificateId; });
		const FSailSave::FCheckrideRecord* Ride = Prog.FindCheckride(T.Checkride.Id);
		FString RideLine = bHeld ? FString::Printf(TEXT("%s earned %s."), *T.CertificateName, Cert ? *ShortDate(Cert->EarnedAt, true) : TEXT(""))
			: (bReady ? FString::Printf(TEXT("Ready: every lesson at %s or better. The written part is %d questions; %.0f%% passes."), *FCareerContent::MedalName(T.Checkride.MinMedal).ToLower(),
				T.Checkride.Quiz.Questions, T.Checkride.Quiz.Pass * 100.0) : Why);
		if (!RideLine.IsEmpty() && !RideLine.EndsWith(TEXT("."))) RideLine += TEXT(".");
		if (Ride && Ride->QuizOf > 0 && !bHeld) RideLine += FString::Printf(TEXT(" Best so far %d of %d."), Ride->QuizBest, Ride->QuizOf);
		// Easy mode earns at most bronze: a checkride that asks for more needs the lessons sailed on Realistic.
		const ECareerMedal EasyMax = FCareerContent::Get().EasyMaxMedal;
		if (!bHeld && !bReady && T.Checkride.MinMedal > EasyMax)
			RideLine += FString::Printf(TEXT(" The checkride needs %s: sail the lessons on Realistic (Easy earns at most %s)."),
				*FCareerContent::MedalName(T.Checkride.MinMedal).ToLower(), *FCareerContent::MedalName(EasyMax).ToLower());
		// Free Sail grades nothing: the checkride waits for Career mode.
		const bool bFree = Career.IsFreeSail();
		if (bFree && !bHeld) RideLine = TEXT("Free Sail: lessons sail without medals. Choose Career on the title screen to earn medals and take the checkride.");
		const FString TierId = T.Id;
		TSharedRef<SSailButton> Take = ActionButton(bHeld ? TEXT("Retake the written checkride") : TEXT("Take the written checkride"),
			FSimpleDelegate::CreateLambda([this, TierId]() { CheckrideTierId = TierId; Quiz.Reset(); Push(ESailScreen::Quiz); }));
		Detail->AddSlot().AutoHeight().Padding(0.f, 10.f, 0.f, 0.f)
		[
			PanelBox(SNew(SVerticalBox)
				+ SVerticalBox::Slot().AutoHeight()
				[
					SNew(SHorizontalBox)
					+ SHorizontalBox::Slot().FillWidth(1.f)[ SailUI::Text(T.Checkride.Title.IsEmpty() ? FString(TEXT("Checkride")) : T.Checkride.Title, EType::CardTitleS, Fg) ]
					+ SHorizontalBox::Slot().AutoWidth()[ Pill(bHeld ? TEXT("Certified") : (bReady ? TEXT("Ready") : TEXT("Not yet")), bHeld || bReady) ]
				]
				+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 6.f, 0.f, 10.f)[ SailUI::Text(RideLine, EType::Body, Muted, true) ]
				+ SVerticalBox::Slot().AutoHeight()[ SNew(SBox).WidthOverride(360.f).HAlign(HAlign_Left).Visibility(bReady && !bFree ? EVisibility::Visible : EVisibility::Collapsed)[ Take ] ],
				FMargin(18.f, 14.f))
		];
	}

	E.Content = SNew(SVerticalBox)
		+ SVerticalBox::Slot().AutoHeight()[ Header(Content.School.IsEmpty() ? FString(TEXT("Career")) : Content.School, TEXT("Learn to sail"), 0) ]
		+ SVerticalBox::Slot().FillHeight(1.f).Padding(0.f, 24.f, 0.f, 90.f)
		[
			SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().FillWidth(0.36f).Padding(0.f, 0.f, 24.f, 0.f)[ SNew(SScrollBox) + SScrollBox::Slot()[ Tiers ] ]
			+ SHorizontalBox::Slot().FillWidth(0.64f)[ SNew(SScrollBox) + SScrollBox::Slot()[ PanelBox(Detail, FMargin(24.f)) ] ]
		];
	E.Footer = PromptBar({ Prompt(TEXT("Enter"), TEXT("A"), TEXT("Choose")), Prompt(TEXT("Esc"), TEXT("B"), TEXT("Back")) },
		SailCareer::IsFreeSail() ? TEXT("Free Sail: lessons sail without medals") : TEXT("A lesson sails its drill; Free Sail on the title opens everything"));
	return E;
}

// ---------------------------------------------------------------- modal confirm

SSailFrontEnd::FEntry SSailFrontEnd::BuildConfirm()
{
	using namespace SailUI;
	using namespace SailFrontEndImpl;
	FEntry E;
	TSharedRef<SSailButton> Yes = ActionButton(ConfirmYes, FSimpleDelegate::CreateLambda([this]() { TFunction<void()> Do = ConfirmAction; Pop(); if (Do) Do(); }));
	TSharedRef<SSailButton> No = ActionButton(ConfirmNo.IsEmpty() ? FString(TEXT("Cancel")) : ConfirmNo,
		FSimpleDelegate::CreateLambda([this]() { TFunction<void()> Do = ConfirmNoAction; Pop(); if (Do) Do(); }), false);
	E.Content = SNew(SBox).HAlign(HAlign_Center).VAlign(VAlign_Center)
	[
		SNew(SBox).WidthOverride(560.f)
		[
			PanelBox(SNew(SVerticalBox)
				+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(ConfirmQuestion, EType::CardTitleM, Fg, true) ]
				+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 24.f, 0.f, 0.f)
				[
					SNew(SHorizontalBox)
					+ SHorizontalBox::Slot().FillWidth(1.f).Padding(0.f, 0.f, 12.f, 0.f)[ Yes ]
					+ SHorizontalBox::Slot().FillWidth(1.f)[ No ]
				], FMargin(28.f))
		]
	];
	E.Focus = No;
	E.Footer = PromptBar({ Prompt(TEXT("Enter"), TEXT("A"), TEXT("Select")), Prompt(TEXT("Esc"), TEXT("B"), TEXT("Cancel")) }, FString());
	return E;
}
