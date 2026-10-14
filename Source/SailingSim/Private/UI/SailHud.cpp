#include "UI/SailHud.h"
#include "UI/SailWidgets.h"
#include "UI/SailCatalog.h"
#include "SailboatPawn.h"
#include "SailingGameMode.h"
#include "SailingHUD.h"
#include "SailingSettings.h"
#include "SailSession.h"
#include "Drills.h"
#include "PolarReference.h"
#include "Weather.h"
#include "Engine/Texture2D.h"
#include "GameFramework/PlayerController.h"
#include "Rendering/DrawElements.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SLeafWidget.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"

using namespace Sailing;

int32 SSailHud::Mode = 0;

namespace SailHudImpl
{
	using namespace SailUI;

	/** Target speed for the true wind and angle, from the boat's reference polar (bilinear in TWS and TWA). */
	double TargetKnots(int32 Type, double Tws, double TwaDeg)
	{
		const std::vector<FPolarPoint>& P = FleetReferencePolar(EBoatType(Type));
		TwaDeg = FMath::Abs(TwaDeg);
		double Best = 0.0, BestW = 0.0;
		for (const FPolarPoint& Pt : P)
		{
			if (Pt.bSpinnaker) continue;
			const double D = FMath::Square((Pt.TrueWindKnots - Tws) / 4.0) + FMath::Square((Pt.TrueWindAngleDeg - TwaDeg) / 20.0);
			const double W = 1.0 / (0.05 + D);
			Best += W * Pt.BoatSpeedKnots * (Tws / FMath::Max(Pt.TrueWindKnots, 1.0) * 0.4 + 0.6);
			BestW += W;
		}
		return BestW > 0.0 ? Best / BestW : 0.0;
	}

	/** The compass tape (5.8): a 5-degree tick, numbers every 30, cardinals in yellow, the true wind mark, a caret. */
	class SCompassTape : public SLeafWidget
	{
	public:
		SLATE_BEGIN_ARGS(SCompassTape) {}
			SLATE_ATTRIBUTE(float, Heading)
			SLATE_ATTRIBUTE(float, WindFrom)
		SLATE_END_ARGS()
		void Construct(const FArguments& A) { Heading = A._Heading; WindFrom = A._WindFrom; }
		virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D(650, 50); }
		virtual int32 OnPaint(const FPaintArgs&, const FGeometry& G, const FSlateRect&, FSlateWindowElementList& Out, int32 Layer, const FWidgetStyle&, bool) const override
		{
			const FVector2D S = G.GetLocalSize();
			const float H = Heading.Get(0.f), PxPerDeg = S.X / 120.f, Cx = S.X * 0.5f;
			FSlateDrawElement::MakeBox(Out, Layer, G.ToPaintGeometry(), Rounded(IsLow() ? PanelSolid : Panel, RadiusButton), ESlateDrawEffect::None, IsLow() ? PanelSolid : Panel);
			for (int32 D = FMath::FloorToInt((H - 62.f) / 5.f) * 5; D <= H + 62.f; D += 5)
			{
				const float X = Cx + (D - H) * PxPerDeg;
				const float Fade = FMath::Clamp(1.f - FMath::Abs(X - Cx) / (S.X * 0.5f), 0.f, 1.f);
				const int32 N = ((D % 360) + 360) % 360;
				const bool bBig = N % 30 == 0;
				FSlateDrawElement::MakeLines(Out, Layer + 1, G.ToPaintGeometry(), { FVector2f(X, S.Y - 2.f), FVector2f(X, S.Y - (bBig ? 14.f : 7.f)) }, ESlateDrawEffect::None, Muted.CopyWithNewOpacity(Fade), true, 1.f);
				if (bBig)
				{
					const TCHAR* Card = N == 0 ? TEXT("N") : N == 90 ? TEXT("E") : N == 180 ? TEXT("S") : N == 270 ? TEXT("W") : nullptr;
					const FString L = Card ? FString(Card) : FString::FromInt(N);
					FSlateDrawElement::MakeText(Out, Layer + 1, G.ToPaintGeometry(FVector2f(40.f, 20.f), FSlateLayoutTransform(FVector2f(X - L.Len() * 4.f, 6.f))), L, Font(EType::Label),
						ESlateDrawEffect::None, (Card ? Accent : Fg).CopyWithNewOpacity(Fade));
				}
			}
			// The true wind: where it comes from.
			float W = FMath::Fmod(WindFrom.Get(0.f) - H + 540.f, 360.f) - 180.f;
			if (FMath::Abs(W) < 60.f)
			{
				const float X = Cx + W * PxPerDeg;
				FSlateDrawElement::MakeLines(Out, Layer + 2, G.ToPaintGeometry(), { FVector2f(X - 6.f, 2.f), FVector2f(X, 12.f), FVector2f(X + 6.f, 2.f) }, ESlateDrawEffect::None, WindTrue, true, 2.5f);
			}
			FSlateDrawElement::MakeLines(Out, Layer + 3, G.ToPaintGeometry(), { FVector2f(Cx - 7.f, S.Y), FVector2f(Cx, S.Y - 10.f), FVector2f(Cx + 7.f, S.Y) }, ESlateDrawEffect::None, Accent, true, 2.5f);
			return Layer + 3;
		}
	private:
		TAttribute<float> Heading, WindFrom;
	};

	/** The apparent wind dial: boat outline, port (red) and starboard (green) close-hauled sectors, the no-go zone,
	 *  the apparent wind arrow (yellow) and a true wind tick. */
	class SWindDialHud : public SLeafWidget
	{
	public:
		SLATE_BEGIN_ARGS(SWindDialHud) {}
			SLATE_ATTRIBUTE(float, Awa)
			SLATE_ATTRIBUTE(float, Twa)
		SLATE_END_ARGS()
		void Construct(const FArguments& A) { Awa = A._Awa; Twa = A._Twa; }
		virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D(200, 200); }
		virtual int32 OnPaint(const FPaintArgs&, const FGeometry& G, const FSlateRect&, FSlateWindowElementList& Out, int32 Layer, const FWidgetStyle&, bool) const override
		{
			const FVector2D S = G.GetLocalSize();
			const FVector2f C(S.X * 0.5f, S.Y * 0.5f - 8.f);
			const float R = FMath::Min(S.X, S.Y) * 0.40f;
			auto Pt = [&](float Deg, float Rad) { const float A = FMath::DegreesToRadians(Deg); return C + FVector2f(FMath::Sin(A) * Rad, -FMath::Cos(A) * Rad); };
			auto Arc = [&](float A0, float A1, float Rad, const FLinearColor& Col, float W)
			{
				TArray<FVector2f> P;
				for (float A = A0; A <= A1 + 0.01f; A += 2.f) P.Add(Pt(A, Rad));
				FSlateDrawElement::MakeLines(Out, Layer, G.ToPaintGeometry(), P, ESlateDrawEffect::None, Col, true, W);
			};
			Arc(0.f, 360.f, R, Line, 2.f);
			Arc(-20.f, 20.f, R - 5.f, Muted.CopyWithNewOpacity(0.6f), 7.f);
			Arc(20.f, 60.f, R - 5.f, Starboard, 7.f);
			Arc(-60.f, -20.f, R - 5.f, Port, 7.f);
			for (int32 D = 0; D < 360; D += 30) FSlateDrawElement::MakeLines(Out, Layer, G.ToPaintGeometry(), { Pt(D, R - 12.f), Pt(D, R - 2.f) }, ESlateDrawEffect::None, Muted, true, 1.f);
			// The boat.
			const TArray<FVector2f> Hull = { C + FVector2f(0.f, -R * 0.45f), C + FVector2f(R * 0.14f, -R * 0.1f), C + FVector2f(R * 0.12f, R * 0.38f),
				C + FVector2f(-R * 0.12f, R * 0.38f), C + FVector2f(-R * 0.14f, -R * 0.1f), C + FVector2f(0.f, -R * 0.45f) };
			FSlateDrawElement::MakeLines(Out, Layer + 1, G.ToPaintGeometry(), Hull, ESlateDrawEffect::None, Fg, true, 2.f);
			// True wind tick, apparent wind arrow.
			const float T = Twa.Get(0.f), A = Awa.Get(0.f);
			FSlateDrawElement::MakeLines(Out, Layer + 2, G.ToPaintGeometry(), { Pt(T, R + 2.f), Pt(T, R - 14.f) }, ESlateDrawEffect::None, WindTrue, true, 4.f);
			const FVector2f Tail = Pt(A, R - 2.f), Head = Pt(A, R * 0.5f);
			const FVector2f D = (Head - Tail).GetSafeNormal(), Sd(-D.Y, D.X);
			FSlateDrawElement::MakeLines(Out, Layer + 3, G.ToPaintGeometry(), { Tail, Head }, ESlateDrawEffect::None, Accent, true, 3.5f);
			FSlateDrawElement::MakeLines(Out, Layer + 3, G.ToPaintGeometry(), { Head - D * 10.f + Sd * 7.f, Head, Head - D * 10.f - Sd * 7.f }, ESlateDrawEffect::None, Accent, true, 3.5f);
			return Layer + 3;
		}
	private:
		TAttribute<float> Awa, Twa;
	};

	/** North-up chart crop around the boat (the launch map), the boat, the true wind. */
	class SMiniMap : public SLeafWidget
	{
	public:
		SLATE_BEGIN_ARGS(SMiniMap) {}
			SLATE_ARGUMENT(TWeakObjectPtr<APlayerController>, Player)
			SLATE_ARGUMENT(TSharedPtr<FSlateBrush>, Map)
		SLATE_END_ARGS()
		void Construct(const FArguments& A) { Player = A._Player; Map = A._Map; }
		virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D(210, 210); }
		virtual int32 OnPaint(const FPaintArgs&, const FGeometry& G, const FSlateRect&, FSlateWindowElementList& Out, int32 Layer, const FWidgetStyle&, bool) const override
		{
			const FVector2D S = G.GetLocalSize();
			FSlateDrawElement::MakeBox(Out, Layer, G.ToPaintGeometry(), Rounded(Water, 14.f, Line, 2.f), ESlateDrawEffect::None, Water);
			const ASailboatPawn* Boat = Player.IsValid() ? Cast<ASailboatPawn>(Player->GetPawn()) : nullptr;
			const ASailingGameMode* GM = Player.IsValid() ? Player->GetWorld()->GetAuthGameMode<ASailingGameMode>() : nullptr;
			if (!Boat || !GM || !Map.IsValid() || Map->ImageSize.X <= 0) return Layer;
			const SailCatalog::FWorld& W = SailCatalog::World(USailingSettings::Get()->World);
			if (USailingSettings::Get()->World == 2) return Layer;   // the Gulf has no baked map
			const FVector2D P = Boat->GetMapPosition();
			const float U = float((P.Y - W.GridEast) / W.GridWidthM), V = float(1.0 - (P.X - W.GridNorth) / W.GridHeightM);
			// About 3 km across.
			const float SpanU = 3000.f / float(W.GridWidthM), SpanV = 3000.f / float(W.GridHeightM);
			FSlateBrush Crop = *Map;
			Crop.SetUVRegion(FBox2f(FVector2f(U - SpanU * 0.5f, V - SpanV * 0.5f), FVector2f(U + SpanU * 0.5f, V + SpanV * 0.5f)));
			FSlateDrawElement::MakeBox(Out, Layer + 1, G.ToPaintGeometry(FVector2f(S.X - 8.f, S.Y - 8.f), FSlateLayoutTransform(FVector2f(4.f, 4.f))), &Crop, ESlateDrawEffect::None, FLinearColor::White);
			const FVector2f C(S.X * 0.5f, S.Y * 0.5f);
			const float H = FMath::DegreesToRadians(float(Boat->GetHeadingTrueDeg()));
			const FVector2f F(FMath::Sin(H), -FMath::Cos(H)), Sd(-F.Y, F.X);
			FSlateDrawElement::MakeLines(Out, Layer + 2, G.ToPaintGeometry(), { C + F * 11.f, C - F * 8.f + Sd * 7.f, C - F * 4.f, C - F * 8.f - Sd * 7.f, C + F * 11.f },
				ESlateDrawEffect::None, Accent, true, 3.f);
			const float Wd = FMath::DegreesToRadians(float(GM->GetWeatherState().Wind.FromDegrees));
			const FVector2f WF(FMath::Sin(Wd), -FMath::Cos(Wd));
			const FVector2f Tip = FVector2f(S.X - 28.f, 28.f);
			FSlateDrawElement::MakeLines(Out, Layer + 2, G.ToPaintGeometry(), { Tip + WF * 16.f, Tip - WF * 12.f }, ESlateDrawEffect::None, WindTrue, true, 3.f);
			FSlateDrawElement::MakeText(Out, Layer + 2, G.ToPaintGeometry(FVector2f(20.f, 20.f), FSlateLayoutTransform(FVector2f(10.f, 8.f))), FString(TEXT("N")), Font(EType::Label), ESlateDrawEffect::None, Ink);
			return Layer + 2;
		}
	private:
		TWeakObjectPtr<APlayerController> Player;
		TSharedPtr<FSlateBrush> Map;
	};

	/** Telltales: a streamer per state (flowing straight, lifting with a curl, or drooping) and the heel bar. */
	class STrimView : public SLeafWidget
	{
	public:
		SLATE_BEGIN_ARGS(STrimView) {}
			SLATE_ARGUMENT(TWeakObjectPtr<APlayerController>, Player)
		SLATE_END_ARGS()
		void Construct(const FArguments& A) { Player = A._Player; }
		virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D(258, 96); }
		virtual int32 OnPaint(const FPaintArgs&, const FGeometry& G, const FSlateRect&, FSlateWindowElementList& Out, int32 Layer, const FWidgetStyle&, bool) const override
		{
			const ASailboatPawn* Boat = Player.IsValid() ? Cast<ASailboatPawn>(Player->GetPawn()) : nullptr;
			if (!Boat) return Layer;
			const FBoatTelemetry& T = Boat->GetBoatModel().GetTelemetry();
			const FVector2D S = G.GetLocalSize();
			auto Count = [](const FSailStripState* St, int32 N, ESailFlow F) { int32 K = 0; for (int32 I = 0; I < N; ++I) K += St[I].Flow == F; return K; };
			const int32 JibLuff = Count(T.JibStrips, T.NumJibStrips, ESailFlow::Luffing) + Count(T.JibStrips, T.NumJibStrips, ESailFlow::Backed);
			const int32 JibStall = Count(T.JibStrips, T.NumJibStrips, ESailFlow::Stalled);
			const int32 MainStall = Count(T.MainStrips, T.NumMainStrips, ESailFlow::Stalled);
			const float Time = float(FPlatformTime::Seconds());
			// A streamer: straight when flowing, a curl when lifting (windward) or stalled, colour by side.
			auto Streamer = [&](float Y, const FLinearColor& Col, bool bFlow, float Phase)
			{
				TArray<FVector2f> P;
				for (int32 I = 0; I <= 24; ++I)
				{
					const float X = 120.f + I * 5.f;
					const float Wob = bFlow ? FMath::Sin(Time * 9.f + I * 0.6f + Phase) * 1.2f : FMath::Sin(Time * 4.f + I * 0.45f + Phase) * (2.f + I * 0.5f);
					P.Add(FVector2f(X, Y + Wob + (bFlow ? 0.f : I * 0.6f)));
				}
				FSlateDrawElement::MakeLines(Out, Layer, G.ToPaintGeometry(), P, ESlateDrawEffect::None, Col, true, 2.5f);
			};
			auto Label = [&](float Y, const FString& L) { FSlateDrawElement::MakeText(Out, Layer, G.ToPaintGeometry(FVector2f(110.f, 18.f), FSlateLayoutTransform(FVector2f(0.f, Y - 9.f))), L, Font(EType::Small), ESlateDrawEffect::None, Muted); };
			const bool bStbd = T.TrueWindAngle > 0.0;
			if (T.NumJibStrips > 0)
			{
				Label(12.f, TEXT("Jib"));
				Streamer(6.f, bStbd ? Starboard : Port, JibLuff < 2, 0.f);       // windward
				Streamer(18.f, bStbd ? Port : Starboard, JibStall < 2, 1.3f);    // leeward
			}
			Label(42.f, TEXT("Main leech"));
			Streamer(42.f, Fg, MainStall < 2, 2.1f);
			// Heel: the boat's comfortable band in green, the boat's heel marker.
			const double Heel = FMath::Abs(FMath::RadiansToDegrees(T.Heel));
			const FBoatConfig& Cfg = Boat->GetBoatModel().GetConfig();
			const float Lo = Cfg.bMultihull ? 0.f : float(Cfg.TrimHeelLimitDeg) * 0.55f, Hi = Cfg.bMultihull ? 5.f : float(Cfg.TrimHeelLimitDeg) * 0.85f;
			Label(76.f, FString::Printf(TEXT("Heel %.0f°"), Heel));
			const float X0 = 120.f, Wd = S.X - 124.f, Y = 72.f, Max = 35.f;
			FSlateDrawElement::MakeBox(Out, Layer, G.ToPaintGeometry(FVector2f(Wd, 6.f), FSlateLayoutTransform(FVector2f(X0, Y))), Rounded(Line, 3.f), ESlateDrawEffect::None, Line);
			FSlateDrawElement::MakeBox(Out, Layer + 1, G.ToPaintGeometry(FVector2f(Wd * (Hi - Lo) / Max, 6.f), FSlateLayoutTransform(FVector2f(X0 + Wd * Lo / Max, Y))), Rounded(Starboard, 3.f), ESlateDrawEffect::None, Starboard.CopyWithNewOpacity(0.8f));
			const float M = X0 + Wd * FMath::Clamp(float(Heel) / Max, 0.f, 1.f);
			FSlateDrawElement::MakeLines(Out, Layer + 2, G.ToPaintGeometry(), { FVector2f(M, Y - 6.f), FVector2f(M, Y + 12.f) }, ESlateDrawEffect::None, Heel > Cfg.TrimHeelLimitDeg ? Warn : Fg, true, 3.f);
			return Layer + 2;
		}
	private:
		TWeakObjectPtr<APlayerController> Player;
	};

	TSharedRef<SWidget> Field(const FString& Label, TAttribute<FText> Value)
	{
		return SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(Label, EType::Label, Muted) ]
			+ SVerticalBox::Slot().AutoHeight()[ TextAttr(Value, EType::Value, FSlateColor(Fg)) ];
	}

	FString KeyName(FName Action, bool bNegative)
	{
		for (const FSailingKeyBinding& B : GetDefault<USailingInputSettings>()->GetBindings())
		{
			if (B.Action == Action && (B.Scale < 0.f) == bNegative && !B.Key.IsGamepadKey() && !B.Key.IsMouseButton() && !B.Key.IsAxis1D() && !B.Key.IsAxis2D())
				return B.Key.GetDisplayName().ToString();
		}
		return TEXT("?");
	}
}

void SSailHud::Construct(const FArguments& A)
{
	using namespace SailUI;
	using namespace SailHudImpl;
	Player = A._Player;
	RegisterInputTracker();
	const SailCatalog::FWorld& W = SailCatalog::World(USailingSettings::Get()->World);
	UTexture2D* Tex = SailUI::KeptTexture(W.MapTexture);
	MapBrush = MakeShared<FSlateBrush>();
	if (Tex) { MapBrush->SetResourceObject(Tex); MapBrush->ImageSize = FVector2D(Tex->GetSizeX(), Tex->GetSizeY()); }
	auto Full = [](){ return Mode == 0 ? EVisibility::HitTestInvisible : EVisibility::Collapsed; };
	auto NotOff = [](){ return Mode < 2 ? EVisibility::HitTestInvisible : EVisibility::Collapsed; };
	auto Heading = [this]() { const ASailboatPawn* P = Pawn(); return P ? float(P->GetHeadingTrueDeg()) : 0.f; };
	auto WindFrom = [this]() { const ASailboatPawn* P = Pawn(); const ASailingGameMode* GM = P ? P->GetWorld()->GetAuthGameMode<ASailingGameMode>() : nullptr; return GM ? float(GM->GetWeatherState().Wind.FromDegrees) : 0.f; };
	auto Awa = [this]() { const ASailboatPawn* P = Pawn(); return P ? float(FMath::RadiansToDegrees(P->GetBoatModel().GetTelemetry().ApparentWindAngle)) : 0.f; };
	auto Twa = [this]() { const ASailboatPawn* P = Pawn(); return P ? float(FMath::RadiansToDegrees(P->GetBoatModel().GetTelemetry().TrueWindAngle)) : 0.f; };
	const float M = HudMargin;
	ChildSlot
	[
		SNew(SOverlay).Visibility_Lambda([this]()
		{
			const ASailboatPawn* P = Pawn();
			const bool bHide = !P || P->IsCaptureMode() || P->IsPhotoMode() || P->IsWatching() || P->IsChartOpen() || P->IsLogOpen() || P->IsKeysOpen()
				|| P->IsMenuOpen() || P->IsControlsCardOpen() || P->IsHeldByUI() || !USailingSettings::Get()->bShowHud;
			return bHide ? EVisibility::Collapsed : EVisibility::HitTestInvisible;
		})
		// Top-left: the environment strip and the tip card.
		+ SOverlay::Slot().HAlign(HAlign_Left).VAlign(VAlign_Top).Padding(M)
		[
			SNew(SVerticalBox).Visibility_Lambda(Full)
			+ SVerticalBox::Slot().AutoHeight()
			[
				PanelBox(SNew(SHorizontalBox)
					+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 22.f, 0.f)[ Field(TEXT("Time"), TAttribute<FText>::CreateLambda([this]() { return TimeText; })) ]
					+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 22.f, 0.f)[ Field(TEXT("True wind"), TAttribute<FText>::CreateLambda([this]() { return WindText; })) ]
					+ SHorizontalBox::Slot().AutoWidth().Padding(0.f, 0.f, 22.f, 0.f)[ Field(TEXT("Sky"), TAttribute<FText>::CreateLambda([this]() { return SkyText; })) ]
					+ SHorizontalBox::Slot().AutoWidth()[ SNew(SBox).Visibility_Lambda([this]() { return bTidal ? EVisibility::Visible : EVisibility::Collapsed; })
						[ Field(TEXT("Tide"), TAttribute<FText>::CreateLambda([this]() { return TideText; })) ] ], FMargin(16.f, 10.f))
			]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 12.f, 0.f, 0.f)
			[
				SNew(SBox).WidthOverride(400.f).Visibility_Lambda([this]() { return bTip ? EVisibility::Visible : EVisibility::Collapsed; })
				[
					SNew(SHorizontalBox)
					+ SHorizontalBox::Slot().AutoWidth()[ SNew(SBox).WidthOverride(4.f)[ SNew(SBorder).BorderImage(Rounded(Accent, 2.f)) ] ]
					+ SHorizontalBox::Slot().FillWidth(1.f)
					[
						PanelBox(SNew(SVerticalBox)
							+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(TEXT("Learning tip"), EType::Eyebrow, Accent) ]
							+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 6.f, 0.f, 4.f)[ TextAttr(TAttribute<FText>::CreateLambda([this]() { return TipTitle; }), EType::Ui, FSlateColor(Fg), true) ]
							+ SVerticalBox::Slot().AutoHeight()[ TextAttr(TAttribute<FText>::CreateLambda([this]() { return TipBody; }), EType::Small, FSlateColor(Muted), true) ]
							+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 8.f, 0.f, 0.f)[ SailUI::Text(TEXT("Hide tips with H · Tips off in Game mode"), EType::Small, Dim) ],
							FMargin(16.f, 12.f), 4.f)
					]
				]
			]
		]
		// Top-centre: the compass tape, heading and toasts.
		// (Padded clear of the strip and the drill panel: the tape narrows on a 4:3 screen rather than overlapping them.)
		+ SOverlay::Slot().HAlign(HAlign_Center).VAlign(VAlign_Top).Padding(FMargin(M + 560.f, M, M + 400.f, M))
		[
			SNew(SVerticalBox).Visibility_Lambda(NotOff)
			+ SVerticalBox::Slot().AutoHeight()[ SNew(SBox).MaxDesiredWidth(650.f).MinDesiredWidth(260.f).HeightOverride(50.f)[ SNew(SCompassTape).Heading_Lambda(Heading).WindFrom_Lambda(WindFrom) ] ]
			+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0.f, 6.f)[ TextAttr(TAttribute<FText>::CreateLambda([this]() { return HeadingText; }), EType::Value, FSlateColor(Fg)) ]
			+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0.f, 6.f)
			[
				SNew(SHorizontalBox).Visibility_Lambda([this]() { return bToast ? EVisibility::Visible : EVisibility::Collapsed; })
				+ SHorizontalBox::Slot().AutoWidth()[ SNew(SBox).WidthOverride(4.f)[ SNew(SBorder).BorderImage_Lambda([this]() { return Rounded(ToastColor, 2.f); }) ] ]
				+ SHorizontalBox::Slot().AutoWidth()[ PanelBox(TextAttr(TAttribute<FText>::CreateLambda([this]() { return ToastText; }), EType::Ui, FSlateColor(Fg)), FMargin(14.f, 8.f), 4.f) ]
			]
		]
		// Top-right: the drill panel.
		+ SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Top).Padding(M)
		[
			SNew(SBox).WidthOverride(365.f).Visibility_Lambda([this]() { return bDrill && Mode < 2 ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
			[
				PanelBox(SNew(SVerticalBox)
					+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(TEXT("ASA 101 drill"), EType::Eyebrow, Accent) ]
					+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 4.f, 0.f, 10.f)[ TextAttr(TAttribute<FText>::CreateLambda([this]() { return DrillTitle; }), EType::CardTitleS, FSlateColor(Fg)) ]
					+ SVerticalBox::Slot().AutoHeight()[ SAssignNew(DrillList, SVerticalBox) ]
					+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 10.f, 0.f, 0.f)[ TextAttr(TAttribute<FText>::CreateLambda([this]() { return DrillFooter; }), EType::Small, FSlateColor(Muted), true) ],
					FMargin(18.f, 14.f))
			]
		]
		// Bottom-left: the minimap.
		+ SOverlay::Slot().HAlign(HAlign_Left).VAlign(VAlign_Bottom).Padding(M)
		[ SNew(SBox).WidthOverride(210.f).HeightOverride(210.f).Visibility_Lambda(Full)[ SNew(SMiniMap).Player(Player).Map(MapBrush) ] ]
		// Bottom-centre: speed, apparent wind, depth.
		+ SOverlay::Slot().HAlign(HAlign_Center).VAlign(VAlign_Bottom).Padding(M)
		[
			SNew(SHorizontalBox).Visibility_Lambda(NotOff)
			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Bottom).Padding(0.f, 0.f, 10.f, 0.f)
			[
				SNew(SBox).WidthOverride(200.f)
				[
					PanelBox(SNew(SVerticalBox)
						+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(TEXT("Speed"), EType::Label, Muted) ]
						+ SVerticalBox::Slot().AutoHeight()
						[
							SNew(SHorizontalBox)
							+ SHorizontalBox::Slot().AutoWidth()[ TextAttr(TAttribute<FText>::CreateLambda([this]() { return SpeedText; }), EType::InstrumentBig, FSlateColor(Fg)) ]
							+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Bottom).Padding(6.f, 0.f, 0.f, 10.f)[ SailUI::Text(TEXT("kn"), EType::Small, Muted) ]
						]
						+ SVerticalBox::Slot().AutoHeight()[ TextAttr(TAttribute<FText>::CreateLambda([this]() { return SpeedSub; }), EType::Small, FSlateColor(Muted)) ], FMargin(16.f, 12.f))
				]
			]
			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Bottom).Padding(0.f, 0.f, 10.f, 0.f)
			[
				PanelBox(SNew(SVerticalBox)
					+ SVerticalBox::Slot().AutoHeight()[ SNew(SBox).WidthOverride(180.f).HeightOverride(170.f)[ SNew(SWindDialHud).Awa_Lambda(Awa).Twa_Lambda(Twa) ] ]
					+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)[ TextAttr(TAttribute<FText>::CreateLambda([this]() { return AwaText; }), EType::Value, FSlateColor(Fg)) ]
					+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)[ TextAttr(TAttribute<FText>::CreateLambda([this]() { return AwsText; }), EType::Label, FSlateColor(Muted)) ], FMargin(10.f, 8.f))
			]
			+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Bottom)
			[
				SNew(SBox).WidthOverride(200.f)
				[
					SNew(SBorder).BorderImage_Lambda([this]() { return Rounded(IsLow() ? PanelSolid : Panel, RadiusCard, bShallow ? Warn : Line, bShallow ? 2.f : 1.f); }).Padding(FMargin(16.f, 12.f))
					[
						SNew(SVerticalBox)
						+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(TEXT("Depth"), EType::Label, Muted) ]
						+ SVerticalBox::Slot().AutoHeight()
						[
							SNew(SHorizontalBox)
							+ SHorizontalBox::Slot().AutoWidth()[ TextAttr(TAttribute<FText>::CreateLambda([this]() { return DepthText; }), EType::InstrumentBig, TAttribute<FSlateColor>::CreateLambda([this]() { return FSlateColor(bShallow ? Warn : Fg); })) ]
							+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Bottom).Padding(6.f, 0.f, 0.f, 10.f)[ SailUI::Text(TEXT("ft"), EType::Small, Muted) ]
						]
						+ SVerticalBox::Slot().AutoHeight()[ TextAttr(TAttribute<FText>::CreateLambda([this]() { return DepthSub; }), EType::Small, FSlateColor(Muted)) ]
					]
				]
			]
		]
		// Bottom-right: sail trim and key hints.
		+ SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Bottom).Padding(M)
		[
			SNew(SVerticalBox).Visibility_Lambda(Full)
			+ SVerticalBox::Slot().AutoHeight()
			[
				SNew(SBox).WidthOverride(290.f)
				[
					PanelBox(SNew(SVerticalBox)
						+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(TEXT("Sail trim"), EType::Label, Muted) ]
						+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 4.f, 0.f, 10.f)[ TextAttr(TAttribute<FText>::CreateLambda([this]() { return PointText; }), EType::Ui, FSlateColor(Fg)) ]
						+ SVerticalBox::Slot().AutoHeight()[ SNew(STrimView).Player(Player) ], FMargin(16.f, 12.f))
				]
			]
			+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Right).Padding(0.f, 10.f, 0.f, 0.f)
			[ TextAttr(TAttribute<FText>::CreateLambda([this]() { return HintsText; }), EType::Small, FSlateColor(Muted)) ]
		]
	];
	Refresh();
}

ASailboatPawn* SSailHud::Pawn() const
{
	return Player.IsValid() ? Cast<ASailboatPawn>(Player->GetPawn()) : nullptr;
}

void SSailHud::Tick(const FGeometry& G, const double Now, const float Dt)
{
	SCompoundWidget::Tick(G, Now, Dt);
	if (Now >= NextRefresh)
	{
		NextRefresh = Now + (SailUI::IsLow() ? 0.2 : 0.1);
		Refresh();
	}
}

void SSailHud::Refresh()
{
	using namespace SailUI;
	using namespace SailHudImpl;
	ASailboatPawn* P = Pawn();
	const ASailingGameMode* GM = P ? P->GetWorld()->GetAuthGameMode<ASailingGameMode>() : nullptr;
	if (!P || !GM) return;
	const FBoatTelemetry& T = P->GetBoatModel().GetTelemetry();
	const FBoatConfig& Cfg = P->GetBoatModel().GetConfig();
	const FWeatherState& Wx = GM->GetWeatherState();
	const FLakeData& Lake = GM->GetLake();
	TimeText = FText::FromString(SailCatalog::ClockText(float(GM->GetLocalHour())));
	WindText = FText::FromString(FString::Printf(TEXT("%.0f kn %s G%.0f"), T.TrueWindSpeed / kKnot, *USailSessionSubsystem::CompassPoint(float(Wx.Wind.FromDegrees)),
		T.TrueWindSpeed / kKnot * (1.0 + Wx.Wind.GustIntensity)));
	const USailSessionSubsystem* Session = USailSessionSubsystem::Get(P);
	const float TempF = Session && Session->bHasActive ? Session->Active.Conditions.AirTempF : 80.f;
	SkyText = FText::FromString(FString::Printf(TEXT("%s · %.0f°F"), UTF8_TO_TCHAR(WeatherPresetName(GM->GetWeather().GetPreset())), TempF));
	bTidal = Lake.IsTidal();
	if (bTidal)
	{
		const Vec3 O = P->GetBoatModel().OriginPosition();
		const Vec3 Cur = GM->GetCurrentAt(O.X, O.Y);
		const double Kn = FMath::Sqrt(Cur.X * Cur.X + Cur.Y * Cur.Y) / kKnot;
		FTideEvent Next;
		const bool bNext = GM->GetNextTide(Next);
		TideText = FText::FromString(FString::Printf(TEXT("%s %.1f kn"), bNext ? (Next.Type == FTideEvent::High ? TEXT("Flooding") : TEXT("Ebbing")) : TEXT("Tide"), Kn));
	}
	// Heading: magnetic on the coast (its variation), true on the lake.
	const double Hdg = FMath::Fmod(P->GetHeadingTrueDeg() - (bTidal ? Lake.VariationDeg : 0.0) + 720.0, 360.0);
	HeadingText = FText::FromString(FString::Printf(TEXT("%03.0f°%s"), Hdg, bTidal ? TEXT("M") : TEXT("T")));
	const double Twa = FMath::RadiansToDegrees(T.TrueWindAngle);
	SpeedText = FText::FromString(FString::Printf(TEXT("%.1f"), T.SpeedThroughWater / kKnot));
	SpeedSub = FText::FromString(FString::Printf(TEXT("VMG %.1f · target %.1f"), T.VMG / kKnot, TargetKnots(int32(Cfg.Type), T.TrueWindSpeed / kKnot, Twa)));
	const double Awa = FMath::RadiansToDegrees(T.ApparentWindAngle);
	AwaText = FText::FromString(FString::Printf(TEXT("%.0f° %s"), FMath::Abs(Awa), Awa >= 0.0 ? TEXT("S") : TEXT("P")));
	AwsText = FText::FromString(FString::Printf(TEXT("APP WIND · %.1f KN"), T.ApparentWindSpeed / kKnot));
	const double DepthFt = (T.DepthUnderKeel + Cfg.Draft) / 0.3048, DraftFt = Cfg.Draft / 0.3048;
	DepthText = FText::FromString(FString::Printf(TEXT("%.0f"), FMath::Min(DepthFt, 999.0)));
	DepthSub = FText::FromString(FString::Printf(TEXT("Keel %.1f · alarm %.0f"), DraftFt, DraftFt + 2.0));
	bShallow = DepthFt < DraftFt + 2.0;
	PointText = FText::FromString(FString::Printf(TEXT("%s · %s"), *SailingPointOfSail(Twa, T.bInIrons), Twa >= 0.0 ? TEXT("starboard") : TEXT("port")));
	// The tip card: the coach's most pressing tip, kept at least 6 s unless something worse comes up.
	const USailingSettings* S = USailingSettings::Get();
	const bool bTipsOn = S->bLearningMode && (!Session || !Session->bHasActive || Session->Active.bLearningTips);
	TArray<TPair<FString, int32>> Tips;
	SailingCollectTips(*P, P->GetWorld(), Tips);
	const TPair<FString, int32>* Best = nullptr;
	for (int32 I = 1; I < Tips.Num(); ++I) if (!Best || Tips[I].Value > Best->Value) Best = &Tips[I];
	const double Now = FPlatformTime::Seconds();
	if (Best && (Best->Key != LastTip) && (Now - TipShownAt > 6.0 || Best->Value >= 2))
	{
		LastTip = Best->Key;
		TipShownAt = Now;
		const int32 Dot = Best->Key.Find(TEXT(":"));
		TipTitle = FText::FromString(Dot > 0 ? Best->Key.Left(Dot) : Tips[0].Key);
		TipBody = FText::FromString(Dot > 0 ? Best->Key.Mid(Dot + 1).TrimStart() : Best->Key);
	}
	bTip = bTipsOn && !LastTip.IsEmpty();
	// Toasts: the boat's status line, the states that matter (aground, capsized, contact).
	FString Toast = P->GetStatusMessage();
	FLinearColor Col = Starboard;
	if (T.bAground) { Toast = TEXT("Aground: ease the sheets, heel her and back off the way you came"); Col = Port; }
	else if (T.bCapsized) { Toast = Cfg.RightingLever > 0.0 ? TEXT("Capsized: let the sheets go, bow to the wind, X to right her") : TEXT("Capsized: R to start again"); Col = Port; }
	else if (T.bCollision && T.BoatSpeed > 0.25 * kKnot) { Toast = TEXT("Contact!"); Col = Port; }
	else if (bShallow && T.DepthUnderKeel < 1.0) { Toast = TEXT("Shallow water ahead"); Col = Warn; }
	if (Toast != LastToast) { LastToast = Toast; ToastSince = Now; }
	bToast = !Toast.IsEmpty() && Now - ToastSince < 3.6;
	ToastText = FText::FromString(Toast);
	ToastColor = Col;
	// The drill panel.
	const FDrillRunner& D = P->GetDrill();
	bDrill = D.GetDrill() != ESailingDrill::None;
	if (bDrill && DrillList.IsValid())
	{
		DrillTitle = FText::FromString(FString(DrillName(D.GetDrill())).ToUpper());
		DrillFooter = FText::FromString(FString::Printf(TEXT("%s · %s%s"), S->bLearningMode ? TEXT("Learning mode") : TEXT("Game mode"),
			S->Difficulty == ESailingDifficulty::Easy ? TEXT("Easy") : TEXT("Realistic"), D.GetStatus().IsEmpty() ? TEXT("") : *(FString(TEXT(" · ")) + D.GetStatus())));
		TArray<TPair<FString, int32>> Steps;
		for (int32 I = 0; I < D.GetSteps().Num(); ++I) Steps.Add({ D.GetSteps()[I], D.IsComplete() || I < D.GetStep() ? 2 : (I == D.GetStep() ? 1 : 0) });
		if (Steps != DrillSteps)
		{
			DrillSteps = Steps;
			DrillList->ClearChildren();
			for (const TPair<FString, int32>& St : Steps)
			{
				DrillList->AddSlot().AutoHeight().Padding(0.f, 3.f)
				[
					SNew(SHorizontalBox)
					+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Top).Padding(0.f, 3.f, 10.f, 0.f)
					[ SNew(SBox).WidthOverride(12.f).HeightOverride(12.f)[ SNew(SBorder).BorderImage(Rounded(St.Value == 2 ? Starboard : (St.Value == 1 ? Accent : FLinearColor::Transparent), 2.f, St.Value == 0 ? Muted : FLinearColor::Transparent, 1.5f)) ] ]
					+ SHorizontalBox::Slot().FillWidth(1.f)[ SailUI::Text(St.Key, St.Value == 1 ? EType::Ui : EType::Small, St.Value == 2 ? Muted : Fg, true) ]
				];
			}
		}
	}
	// Key hints: up to three, from the situation.
	TArray<FString> Hints;
	if (T.bCapsized && Cfg.RightingLever > 0.0) Hints.Add(KeyName(TEXT("Righting"), false) + TEXT("  Right the boat"));
	Hints.Add(KeyName(TEXT("Tiller"), true) + TEXT(" / ") + KeyName(TEXT("Tiller"), false) + TEXT("  Steer"));
	if (bTidal) Hints.Add(KeyName(TEXT("Chart"), false) + TEXT("  Chart"));
	Hints.Add(KeyName(TEXT("Menu"), false) + TEXT("  Pause"));
	while (Hints.Num() > 3) Hints.RemoveAt(1);
	HintsText = FText::FromString(FString::Join(Hints, TEXT("     ")));
}
