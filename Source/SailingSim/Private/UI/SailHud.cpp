#include "UI/SailHud.h"
#include "Widgets/SInvalidationPanel.h"
#include "PerfScopes.h"
#include "BenchRunner.h"
#include "Learning.h"
#include "UI/SailWidgets.h"
#include "UI/SailCatalog.h"
#include "SailboatPawn.h"
#include "SailingGameMode.h"
#include "SailingHUD.h"
#include "SailingSettings.h"
#include "SailingEnvironment.h"
#include "EngineUtils.h"
#include "Styling/StyleDefaults.h"
#include "Chart.h"
#include "LakeData.h"
#include "SailingBindings.h"
#include "SailSession.h"
#include "Drills.h"
#include "PolarReference.h"
#include "Weather.h"
#include "Navigation.h"
#include "Race.h"
#include "RulesCoach.h"
#include "Tides.h"
#include "TrafficManager.h"
#include "SoundCaptions.h"
#include "SailCloth.h"
#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"
#include "Rendering/SlateRenderer.h"
#include "Engine/Texture2D.h"
#include "GameFramework/PlayerController.h"
#include "Rendering/DrawElements.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SDPIScaler.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SLeafWidget.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"

using namespace Sailing;

int32 SSailHud::Mode = 0;

namespace SailHudImpl
{
	using namespace SailUI;

	/** The night palette's strength now (0 by day, 1 in the dark): SSailHud::Tick sets it, the leaf instruments read it
	 *  as they draw. */
	float NightHud = 0.f;
	FLinearColor NightCol(const FLinearColor& C) { return SSailHud::NightColor(C, NightHud); }
	/** A bright surface at night (the trim windows' cloth and sky, the minimap's chart): red, and dimmed to Share of its
	 *  brightness, so it is not the lamp on the screen and the marks drawn on it stand out. */
	FLinearColor NightDim(const FLinearColor& C, float Share)
	{
		const FLinearColor N = NightCol(C);
		const float K = FMath::Lerp(1.f, Share, NightHud);
		return FLinearColor(N.R * K, N.G * K, N.B * K, N.A);
	}
	/** A text colour's attribute with red lifted to its brightness, so aqua and green words survive the panel's red tint. */
	TAttribute<FSlateColor> NightLift(TAttribute<FSlateColor> Color)
	{
		return TAttribute<FSlateColor>::CreateLambda([Color]()
		{
			const FSlateColor C = Color.Get();
			return NightHud > 0.f && C.IsColorSpecified() ? FSlateColor(SSailHud::NightColor(C.GetSpecifiedColor(), NightHud, false)) : C;
		});
	}

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
			/** UI Natural: no panel behind the tape; its ticks and numbers carry a drop shadow instead. */
			SLATE_ATTRIBUTE(bool, Bare)
		SLATE_END_ARGS()
		void Construct(const FArguments& A) { Heading = A._Heading; WindFrom = A._WindFrom; Bare = A._Bare; ForceVolatile(true); }
		virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D(650, 50); }
		virtual int32 OnPaint(const FPaintArgs&, const FGeometry& G, const FSlateRect&, FSlateWindowElementList& Out, int32 Layer, const FWidgetStyle&, bool) const override
		{
			const FVector2D S = G.GetLocalSize();
			const float H = Heading.Get(0.f), PxPerDeg = S.X / 120.f, Cx = S.X * 0.5f;
			const bool bBare = Bare.Get(false);
			const FVector2f Drop(1.f, 1.5f);
			const FLinearColor DropColor(0.f, 0.f, 0.f, 0.7f);
			if (!bBare) FSlateDrawElement::MakeBox(Out, Layer, G.ToPaintGeometry(), Rounded(IsLow() ? PanelSolid : Panel, RadiusButton), ESlateDrawEffect::None, NightCol(IsLow() ? PanelSolid : Panel));
			for (int32 D = FMath::FloorToInt((H - 62.f) / 5.f) * 5; D <= H + 62.f; D += 5)
			{
				const float X = Cx + (D - H) * PxPerDeg;
				// Bare (UI Natural) the tape has no panel behind it, so it fades later toward its ends and its ticks are heavier.
				const float Edge = FMath::Clamp(1.f - FMath::Abs(X - Cx) / (S.X * 0.5f), 0.f, 1.f);
				const float Fade = bBare ? FMath::Min(1.f, Edge * 2.2f) : Edge;
				const int32 N = ((D % 360) + 360) % 360;
				const bool bBig = N % 30 == 0;
				if (bBare) FSlateDrawElement::MakeLines(Out, Layer, G.ToPaintGeometry(), { FVector2f(X, S.Y - 2.f) + Drop, FVector2f(X, S.Y - (bBig ? 14.f : 7.f)) + Drop }, ESlateDrawEffect::None, NightCol(DropColor.CopyWithNewOpacity(0.8f * Fade)), true, 3.f);
				FSlateDrawElement::MakeLines(Out, Layer + 1, G.ToPaintGeometry(), { FVector2f(X, S.Y - 2.f), FVector2f(X, S.Y - (bBig ? 14.f : 7.f)) }, ESlateDrawEffect::None, NightCol((bBare ? Fg : Muted).CopyWithNewOpacity(Fade)), true, bBare ? 2.f : 1.f);
				if (bBig)
				{
					const TCHAR* Card = N == 0 ? TEXT("N") : N == 90 ? TEXT("E") : N == 180 ? TEXT("S") : N == 270 ? TEXT("W") : nullptr;
					const FString L = Card ? FString(Card) : FString::FromInt(N);
					if (bBare) FSlateDrawElement::MakeText(Out, Layer, G.ToPaintGeometry(FVector2f(40.f, 20.f), FSlateLayoutTransform(FVector2f(X - L.Len() * 4.f, 6.f) + Drop)), L, Font(EType::Label),
						ESlateDrawEffect::None, NightCol(DropColor.CopyWithNewOpacity(0.7f * Fade)));
					FSlateDrawElement::MakeText(Out, Layer + 1, G.ToPaintGeometry(FVector2f(40.f, 20.f), FSlateLayoutTransform(FVector2f(X - L.Len() * 4.f, 6.f))), L, Font(EType::Label),
						ESlateDrawEffect::None, NightCol((Card ? Accent : Fg).CopyWithNewOpacity(Fade)));
				}
			}
			// The true wind: where it comes from.
			float W = FMath::Fmod(WindFrom.Get(0.f) - H + 540.f, 360.f) - 180.f;
			if (FMath::Abs(W) < 60.f)
			{
				const float X = Cx + W * PxPerDeg;
				FSlateDrawElement::MakeLines(Out, Layer + 2, G.ToPaintGeometry(), { FVector2f(X - 6.f, 2.f), FVector2f(X, 12.f), FVector2f(X + 6.f, 2.f) }, ESlateDrawEffect::None, NightCol(WindTrue), true, 2.5f);
			}
			FSlateDrawElement::MakeLines(Out, Layer + 3, G.ToPaintGeometry(), { FVector2f(Cx - 7.f, S.Y), FVector2f(Cx, S.Y - 10.f), FVector2f(Cx + 7.f, S.Y) }, ESlateDrawEffect::None, NightCol(Accent), true, 2.5f);
			return Layer + 3;
		}
	private:
		TAttribute<float> Heading, WindFrom;
		TAttribute<bool> Bare;
	};

	/** The apparent wind dial: boat outline, port (red) and starboard (green) close-hauled sectors, the no-go zone,
	 *  the apparent wind arrow (yellow) and a true wind tick. Around the true wind, the no-go cue at the sim's angle
	 *  (FEasyAssists::NoGoDeg): a thin band on Realistic, a wide one with edge lines on Easy, amber close to it and
	 *  bright inside it (NoGoCueFor). */
	class SWindDialHud : public SLeafWidget
	{
	public:
		SLATE_BEGIN_ARGS(SWindDialHud) {}
			SLATE_ATTRIBUTE(float, Awa)
			SLATE_ATTRIBUTE(float, Twa)
			SLATE_ATTRIBUTE(float, NoGo)
			SLATE_ATTRIBUTE(int32, Cue)
			SLATE_ATTRIBUTE(bool, Wide)
			/** UI Natural: no panel around the dial, so it carries its own round ink face. */
			SLATE_ATTRIBUTE(bool, Bare)
		SLATE_END_ARGS()
		void Construct(const FArguments& A) { Awa = A._Awa; Twa = A._Twa; NoGo = A._NoGo; Cue = A._Cue; Wide = A._Wide; Bare = A._Bare; ForceVolatile(true); }
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
				FSlateDrawElement::MakeLines(Out, Layer, G.ToPaintGeometry(), P, ESlateDrawEffect::None, NightCol(Col), true, W);
			};
			if (Bare.Get(false))
			{
				const float Face = R + 6.f;
				const FLinearColor FaceColor = Ink.CopyWithNewOpacity(0.5f);
				FSlateDrawElement::MakeBox(Out, Layer, G.ToPaintGeometry(FVector2f(Face * 2.f, Face * 2.f), FSlateLayoutTransform(C - FVector2f(Face, Face))), Rounded(FaceColor, Face), ESlateDrawEffect::None, NightCol(FaceColor));
			}
			Arc(0.f, 360.f, R, Line, 2.f);
			Arc(-20.f, 20.f, R - 5.f, Muted.CopyWithNewOpacity(0.6f), 7.f);
			Arc(20.f, 60.f, R - 5.f, Starboard, 7.f);
			Arc(-60.f, -20.f, R - 5.f, Port, 7.f);
			for (int32 D = 0; D < 360; D += 30) FSlateDrawElement::MakeLines(Out, Layer, G.ToPaintGeometry(), { Pt(D, R - 12.f), Pt(D, R - 2.f) }, ESlateDrawEffect::None, NightCol(Muted), true, 1.f);
			// The no-go cue around the true wind.
			{
				const float W = Twa.Get(0.f), Half = NoGo.Get(35.f);
				const bool bWide = Wide.Get(false);
				const int32 CueNow = Cue.Get(0);
				const FLinearColor Col = CueNow == 2 ? Port : (CueNow == 1 ? Warn : Port.CopyWithNewOpacity(bWide ? 0.55f : 0.35f));
				Arc(W - Half, W + Half, R - (bWide ? 17.f : 15.f), Col, bWide ? 10.f : 3.f);
				if (bWide)
				{
					for (const float E : { W - Half, W + Half })
						FSlateDrawElement::MakeLines(Out, Layer, G.ToPaintGeometry(), { Pt(E, R * 0.22f), Pt(E, R - 12.f) }, ESlateDrawEffect::None, NightCol(Col.CopyWithNewOpacity(0.8f)), true, 2.f);
				}
			}
			// The boat.
			const TArray<FVector2f> Hull = { C + FVector2f(0.f, -R * 0.45f), C + FVector2f(R * 0.14f, -R * 0.1f), C + FVector2f(R * 0.12f, R * 0.38f),
				C + FVector2f(-R * 0.12f, R * 0.38f), C + FVector2f(-R * 0.14f, -R * 0.1f), C + FVector2f(0.f, -R * 0.45f) };
			FSlateDrawElement::MakeLines(Out, Layer + 1, G.ToPaintGeometry(), Hull, ESlateDrawEffect::None, NightCol(Fg), true, 2.f);
			// True wind tick, apparent wind arrow.
			const float T = Twa.Get(0.f), A = Awa.Get(0.f);
			FSlateDrawElement::MakeLines(Out, Layer + 2, G.ToPaintGeometry(), { Pt(T, R + 2.f), Pt(T, R - 14.f) }, ESlateDrawEffect::None, NightCol(WindTrue), true, 4.f);
			const FVector2f Tail = Pt(A, R - 2.f), Head = Pt(A, R * 0.5f);
			const FVector2f D = (Head - Tail).GetSafeNormal(), Sd(-D.Y, D.X);
			FSlateDrawElement::MakeLines(Out, Layer + 3, G.ToPaintGeometry(), { Tail, Head }, ESlateDrawEffect::None, NightCol(Accent), true, 3.5f);
			FSlateDrawElement::MakeLines(Out, Layer + 3, G.ToPaintGeometry(), { Head - D * 10.f + Sd * 7.f, Head, Head - D * 10.f - Sd * 7.f }, ESlateDrawEffect::None, NightCol(Accent), true, 3.5f);
			return Layer + 3;
		}
	private:
		TAttribute<float> Awa, Twa, NoGo;
		TAttribute<int32> Cue;
		TAttribute<bool> Wide, Bare;
	};

	/** North-up chart crop around the boat (T_MiniMap_<World>), the boat, the true wind. */
	class SMiniMap : public SLeafWidget
	{
	public:
		SLATE_BEGIN_ARGS(SMiniMap) {}
			SLATE_ARGUMENT(TWeakObjectPtr<APlayerController>, Player)
			SLATE_ARGUMENT(TSharedPtr<FSlateBrush>, Map)
		SLATE_END_ARGS()
		void Construct(const FArguments& A) { Player = A._Player; Map = A._Map; ForceVolatile(true); }
		virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D(210, 210); }
		virtual int32 OnPaint(const FPaintArgs&, const FGeometry& G, const FSlateRect&, FSlateWindowElementList& Out, int32 Layer, const FWidgetStyle&, bool) const override
		{
			// The chart minimap (docs/ui-overhaul/, Phase 7): a small sheet of chart paper with an ink neatline, the chart crop
			// washed toward the paper, the boat in ink with her heading line, a scale bar, north and the true wind. By night
			// the sheet dims and reddens with the rest of the HUD.
			const FVector2D S = G.GetLocalSize();
			const FLinearColor Sheet = NightDim(Paper, 0.3f);
			FSlateDrawElement::MakeBox(Out, Layer, G.ToPaintGeometry(), Rounded(Sheet, 6.f), ESlateDrawEffect::None, Sheet);
			const FVector2f MapOrigin(6.f, 6.f), MapSize(float(S.X) - 12.f, float(S.Y) - 12.f);
			const FLinearColor InkCol = NightCol(FMath::Lerp(PaperInk, Fg, NightHud));                      // marks: ink by day, the text's red by night
			const FLinearColor HaloCol = FMath::Lerp(Paper, Ink, NightHud).CopyWithNewOpacity(0.85f);     // under them: paper by day, ink by night
			auto Neatline = [&]()
			{
				const FVector2f A = MapOrigin, B = MapOrigin + MapSize;
				FSlateDrawElement::MakeLines(Out, Layer + 2, G.ToPaintGeometry(), { A, FVector2f(B.X, A.Y), B, FVector2f(A.X, B.Y), A }, ESlateDrawEffect::None, InkCol.CopyWithNewOpacity(0.7f), true, 1.f);
			};
			const ASailboatPawn* Boat = Player.IsValid() ? Cast<ASailboatPawn>(Player->GetPawn()) : nullptr;
			const ASailingGameMode* GM = Player.IsValid() ? Player->GetWorld()->GetAuthGameMode<ASailingGameMode>() : nullptr;
			if (!Boat || !GM || !Map.IsValid() || Map->ImageSize.X <= 0) { Neatline(); return Layer + 2; }
			const SailCatalog::FMiniMap& W = SailCatalog::MiniMap(USailingSettings::Get()->World);
			const FVector2D P = Boat->GetMapPosition();
			const float U = float((P.Y - W.GridEast) / W.GridWidthM), V = float(1.0 - (P.X - W.GridNorth) / W.GridHeightM);
			// About 3 km across (8 offshore).
			const float SpanU = float(W.SpanM / W.GridWidthM), SpanV = float(W.SpanM / W.GridHeightM);
			FSlateBrush Crop = *Map;
			Crop.SetUVRegion(FBox2f(FVector2f(U - SpanU * 0.5f, V - SpanV * 0.5f), FVector2f(U + SpanU * 0.5f, V + SpanV * 0.5f)));
			FSlateDrawElement::MakeBox(Out, Layer + 1, G.ToPaintGeometry(MapSize, FSlateLayoutTransform(MapOrigin)), &Crop, ESlateDrawEffect::None, NightDim(FLinearColor::White, 0.45f));
			// A light wash of the paper over the print ties it to the sheet (the texture is a pale chart already: Phase 12).
			const FLinearColor Wash = NightDim(Paper, 0.3f).CopyWithNewOpacity(0.08f);
			FSlateDrawElement::MakeBox(Out, Layer + 1, G.ToPaintGeometry(MapSize, FSlateLayoutTransform(MapOrigin)), White(), ESlateDrawEffect::None, Wash);
			Neatline();
			// Aids to navigation inside the crop, in their chart colours (a dot each: the chart page has the symbols).
			{
				int32 Drawn = 0;
				const double Half = W.SpanM * 0.5;
				for (const FNavaid& Aid : GM->GetLake().Navaids)
				{
					if (FMath::Abs(Aid.X - P.X) > Half || FMath::Abs(Aid.Y - P.Y) > Half) continue;
					bool bOff = false;
					const FVector2f Q = SSailHud::MiniMapPoint(P, FVector2D(Aid.X, Aid.Y), W.SpanM, MapOrigin, MapSize, bOff);
					if (bOff) continue;
					const FLinearColor AidCol = NightCol(SailingChart::AidColour(Aid));
					FSlateDrawElement::MakeBox(Out, Layer + 2, G.ToPaintGeometry(FVector2f(7.f, 7.f), FSlateLayoutTransform(Q - FVector2f(3.5f, 3.5f))), Rounded(HaloCol, 3.5f), ESlateDrawEffect::None, HaloCol);
					FSlateDrawElement::MakeBox(Out, Layer + 2, G.ToPaintGeometry(FVector2f(5.f, 5.f), FSlateLayoutTransform(Q - FVector2f(2.5f, 2.5f))), Rounded(AidCol, 2.5f), ESlateDrawEffect::None, AidCol);
					if (++Drawn >= 48) break;
				}
			}
			const FVector2f C = MapOrigin + MapSize * 0.5f;
			const float H = FMath::DegreesToRadians(float(Boat->GetHeadingTrueDeg()));
			const FVector2f F(FMath::Sin(H), -FMath::Cos(H)), Sd(-F.Y, F.X);
			// The boat: her heading line ahead, then her outline in ink over a halo, so she reads on water and on land.
			FSlateDrawElement::MakeLines(Out, Layer + 3, G.ToPaintGeometry(), { C + F * 14.f, C + F * 38.f }, ESlateDrawEffect::None, InkCol.CopyWithNewOpacity(0.85f), true, 1.5f);
			const TArray<FVector2f> Hull = { C + F * 11.f, C - F * 8.f + Sd * 7.f, C - F * 4.f, C - F * 8.f - Sd * 7.f, C + F * 11.f };
			FSlateDrawElement::MakeLines(Out, Layer + 3, G.ToPaintGeometry(), Hull, ESlateDrawEffect::None, HaloCol, true, 7.f);
			FSlateDrawElement::MakeLines(Out, Layer + 4, G.ToPaintGeometry(), Hull, ESlateDrawEffect::None, InkCol, true, 2.5f);
			// The true wind, top right: an arrow flying downwind, in the wind's colour over a halo.
			const float Wd = FMath::DegreesToRadians(float(GM->GetWeatherState().Wind.FromDegrees));
			const FVector2f WF(FMath::Sin(Wd), -FMath::Cos(Wd)), WS(-WF.Y, WF.X);
			const FVector2f Tip = FVector2f(float(S.X) - 30.f, 30.f);
			const FVector2f WHead = Tip - WF * 14.f, WTail = Tip + WF * 14.f;
			const TArray<FVector2f> Shaft = { WTail, WHead };
			const TArray<FVector2f> Barb = { WHead + WF * 8.f + WS * 5.f, WHead, WHead + WF * 8.f - WS * 5.f };
			const FLinearColor WindCol = NightCol(FMath::Lerp(AccentDeep, WindTrue, NightHud));
			FSlateDrawElement::MakeLines(Out, Layer + 3, G.ToPaintGeometry(), Shaft, ESlateDrawEffect::None, HaloCol, true, 6.f);
			FSlateDrawElement::MakeLines(Out, Layer + 3, G.ToPaintGeometry(), Barb, ESlateDrawEffect::None, HaloCol, true, 6.f);
			FSlateDrawElement::MakeLines(Out, Layer + 4, G.ToPaintGeometry(), Shaft, ESlateDrawEffect::None, WindCol, true, 2.5f);
			FSlateDrawElement::MakeLines(Out, Layer + 4, G.ToPaintGeometry(), Barb, ESlateDrawEffect::None, WindCol, true, 2.5f);
			// North, top left: the letter under a small arrowhead.
			FSlateDrawElement::MakeLines(Out, Layer + 3, G.ToPaintGeometry(), { FVector2f(12.f, 16.f), FVector2f(17.f, 9.f), FVector2f(22.f, 16.f) }, ESlateDrawEffect::None, InkCol, true, 1.5f);
			FSlateDrawElement::MakeText(Out, Layer + 3, G.ToPaintGeometry(FVector2f(20.f, 20.f), FSlateLayoutTransform(FVector2f(12.f, 16.f))), FString(TEXT("N")), Font(EType::Label), ESlateDrawEffect::None, InkCol);
			// The scale bar, bottom left: a round length in nautical miles, ticked at its ends.
			{
				float BarPx = 0.f;
				const FString BarText = SSailHud::MiniMapScaleBar(W.SpanM, MapSize.X, BarPx);
				const FVector2f B0 = MapOrigin + FVector2f(8.f, MapSize.Y - 12.f), B1 = B0 + FVector2f(BarPx, 0.f);
				const TArray<FVector2f> Bar = { B0 - FVector2f(0.f, 4.f), B0, B1, B1 - FVector2f(0.f, 4.f) };
				FSlateDrawElement::MakeLines(Out, Layer + 3, G.ToPaintGeometry(), Bar, ESlateDrawEffect::None, HaloCol, true, 5.f);
				FSlateDrawElement::MakeLines(Out, Layer + 4, G.ToPaintGeometry(), Bar, ESlateDrawEffect::None, InkCol, true, 2.f);
				FSlateDrawElement::MakeText(Out, Layer + 3, G.ToPaintGeometry(FVector2f(80.f, 20.f), FSlateLayoutTransform(B0 + FVector2f(1.f, -22.f) + FVector2f(1.f, 1.f))), BarText, Font(EType::Label), ESlateDrawEffect::None, HaloCol);
				FSlateDrawElement::MakeText(Out, Layer + 4, G.ToPaintGeometry(FVector2f(80.f, 20.f), FSlateLayoutTransform(B0 + FVector2f(1.f, -22.f))), BarText, Font(EType::Label), ESlateDrawEffect::None, InkCol);
				// (the ink strokes sit a layer above their halos: within one layer Slate does not keep the order of batches)
			}
			// #602 (the #400 audit): a drill's marks still to round and the person in the water, on the map: a triangle's marks
			// could only be found by the panel's distance, and an overboard drill is about keeping them in sight. The next
			// mark larger; one off the map sits on its edge, so its direction shows. Filled dots under the boat (her arrow
			// and the wind and N labels draw on Layer + 3), so a dummy just astern stays visible past her; an edge dot slides
			// along the edge clear of the N label (top left) and the wind arrow (top right).
			const FDrillRunner& D = Boat->GetDrill();
			if (D.IsActive())
			{
				// Edge dots keep clear of north (top left), the wind arrow (top right) and the scale bar (bottom left).
				const FBox2f Keep[3] = { FBox2f(FVector2f(0.f, 0.f), FVector2f(34.f, 38.f)), FBox2f(FVector2f(float(S.X) - 52.f, 0.f), FVector2f(float(S.X), 52.f)),
					FBox2f(FVector2f(0.f, float(S.Y) - 40.f), FVector2f(96.f, float(S.Y))) };
				auto Dot = [&](const FVector2D& At, float R, const FLinearColor& Col)
				{
					bool bClamped = false;
					FVector2f Q = SSailHud::MiniMapPoint(P, At, W.SpanM, MapOrigin, MapSize, bClamped);
					const float Rd = bClamped ? R * 0.75f : R;
					if (bClamped) Q = SSailHud::MiniMapClearOf(Q, Rd, Keep, MapOrigin, MapSize);
					FSlateDrawElement::MakeBox(Out, Layer + 2, G.ToPaintGeometry(FVector2f(2.f * Rd, 2.f * Rd), FSlateLayoutTransform(Q - FVector2f(Rd, Rd))),
						Rounded(Col, Rd), ESlateDrawEffect::None, NightCol(Col));
				};
				const TArray<FVector2D>& Marks = D.GetMarks();
				for (int32 K = D.GetNextMark(); K < Marks.Num(); ++K) Dot(Marks[K], K == D.GetNextMark() ? 4.5f : 3.f, Warn);
				if (D.HasDummy()) Dot(D.GetDummy(), 4.5f, Port);
			}
			return Layer + 4;
		}
	private:
		TWeakObjectPtr<APlayerController> Player;
		TSharedPtr<FSlateBrush> Map;
	};

	/**
	 * The wrist compass (docs/ui-overhaul/, Phase 8; Bean: "a watch with a compass for a sunfish"): with the interface
	 * off, a glance at the wrist. A brass-cased watch on its strap: the compass card turns under a fixed lubber mark at
	 * twelve, north in red, the heading in figures at the centre and the time under it. It fades up and down with
	 * ASailboatPawn::WristAlpha and reddens with the night palette.
	 */
	class SWristCompass : public SLeafWidget
	{
	public:
		SLATE_BEGIN_ARGS(SWristCompass) {}
			SLATE_ARGUMENT(TWeakObjectPtr<APlayerController>, Player)
		SLATE_END_ARGS()
		void Construct(const FArguments& A) { Player = A._Player; ForceVolatile(true); }
		virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D(164, 204); }
		virtual int32 OnPaint(const FPaintArgs&, const FGeometry& G, const FSlateRect&, FSlateWindowElementList& Out, int32 Layer, const FWidgetStyle&, bool) const override
		{
			const ASailboatPawn* Boat = Player.IsValid() ? Cast<ASailboatPawn>(Player->GetPawn()) : nullptr;
			const ASailingGameMode* GM = Player.IsValid() ? Player->GetWorld()->GetAuthGameMode<ASailingGameMode>() : nullptr;
			const float Alpha = Boat ? Boat->WristAlpha() : 0.f;
			if (!Boat || !GM || Alpha <= 0.f) return Layer;
			auto Col = [Alpha](const FLinearColor& In) { const FLinearColor N = NightCol(In); return N.CopyWithNewOpacity(N.A * Alpha); };
			auto Disc = [&](const FVector2f& At, float R, const FLinearColor& In, int32 L)
			{
				const FLinearColor Tone = Col(In);
				FSlateDrawElement::MakeBox(Out, L, G.ToPaintGeometry(FVector2f(2.f * R, 2.f * R), FSlateLayoutTransform(At - FVector2f(R, R))), Rounded(Tone, R), ESlateDrawEffect::None, Tone);
			};
			const FVector2D S = G.GetLocalSize();
			const FVector2f C(float(S.X) * 0.5f, float(S.Y) * 0.5f);
			// The strap, above and below the case.
			const FLinearColor Strap = Col(Hex(0x0E171E, 0.92f));
			FSlateDrawElement::MakeBox(Out, Layer, G.ToPaintGeometry(FVector2f(84.f, float(S.Y)), FSlateLayoutTransform(FVector2f(C.X - 42.f, 0.f))), Rounded(Strap, 10.f), ESlateDrawEffect::None, Strap);
			// The case: brass, an ink bezel, the dark face.
			Disc(C, 76.f, Brass, Layer + 1);
			Disc(C, 70.f, Ink, Layer + 2);
			Disc(C, 64.f, Hex(0x0B1319), Layer + 3);
			// The card turns under the lubber mark: a tick each 30 degrees, longer at the cardinals, their letters inside.
			const FLakeData& Lake = GM->GetLake();
			const USailingSettings* U = USailingSettings::Get();
			const bool bMagnetic = !U->bHeadingsTrue && Lake.VariationDeg != 0.0;
			const double Hdg = FMath::Fmod(Boat->GetHeadingTrueDeg() - (bMagnetic ? Lake.VariationDeg : 0.0) + 720.0, 360.0);
			auto On = [&](float Deg, float R) { const float A = FMath::DegreesToRadians(Deg - float(Hdg)); return C + FVector2f(FMath::Sin(A), -FMath::Cos(A)) * R; };
			const TSharedRef<FSlateFontMeasure> Measure = FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
			const FSlateFontInfo Small = Font(EType::Label);
			for (int32 D = 0; D < 360; D += 30)
			{
				const bool bCard = D % 90 == 0;
				FSlateDrawElement::MakeLines(Out, Layer + 4, G.ToPaintGeometry(), { On(float(D), 62.f), On(float(D), 58.f) }, ESlateDrawEffect::None, Col(D == 0 ? Port : (bCard ? Fg : Muted)), true, bCard ? 2.f : 1.f);
				if (!bCard) continue;
				const FString Letter = D == 0 ? TEXT("N") : D == 90 ? TEXT("E") : D == 180 ? TEXT("S") : TEXT("W");
				const FVector2D Sz = Measure->Measure(Letter, Small);
				// The letters ride a ring well outside the figures at the centre (they collided with the time at 37 px).
				const FVector2f At = On(float(D), 46.f) - FVector2f(float(Sz.X), float(Sz.Y)) * 0.5f;
				FSlateDrawElement::MakeText(Out, Layer + 4, G.ToPaintGeometry(FVector2f(float(Sz.X) + 2.f, float(Sz.Y)), FSlateLayoutTransform(At)), Letter, Small, ESlateDrawEffect::None, Col(D == 0 ? Port : Fg));
			}
			// The lubber mark at twelve, on the bezel: the way the bow points.
			FSlateDrawElement::MakeLines(Out, Layer + 5, G.ToPaintGeometry(), { C + FVector2f(-6.f, -74.f), C + FVector2f(0.f, -64.f), C + FVector2f(6.f, -74.f) }, ESlateDrawEffect::None, Col(FMath::Lerp(Accent, Fg, NightHud)), true, 2.5f);
			// The heading in figures and the time, at the centre.
			const FSlateFontInfo Big = Font(EType::Value);
			const FString HdgText = FString::Printf(TEXT("%03.0f°"), Hdg >= 359.5 ? 0.0 : Hdg);
			const FVector2D HdgSize = Measure->Measure(HdgText, Big);
			FSlateDrawElement::MakeText(Out, Layer + 5, G.ToPaintGeometry(FVector2f(float(HdgSize.X) + 2.f, float(HdgSize.Y)), FSlateLayoutTransform(C - FVector2f(float(HdgSize.X) * 0.5f, float(HdgSize.Y) * 0.5f + 5.f))), HdgText, Big, ESlateDrawEffect::None, Col(Fg));
			const double Hour = GM->GetLocalHour();
			const FString TimeText = FString::Printf(TEXT("%02d:%02d"), int32(Hour) % 24, int32(FMath::Fmod(Hour, 1.0) * 60.0));
			const FVector2D TimeSize = Measure->Measure(TimeText, Small);
			FSlateDrawElement::MakeText(Out, Layer + 5, G.ToPaintGeometry(FVector2f(float(TimeSize.X) + 2.f, float(TimeSize.Y)), FSlateLayoutTransform(C + FVector2f(-float(TimeSize.X) * 0.5f, float(HdgSize.Y) * 0.5f - 9.f))), TimeText, Small, ESlateDrawEffect::None, Col(Muted));
			return Layer + 5;
		}
	private:
		TWeakObjectPtr<APlayerController> Player;
	};

	/**
	 * The sail trim panel (Bean, Nov 15 2026: the "Telltale window", docs/trim-panel/): a window onto the jib's luff with
	 * three yarn pairs a hand's width aft of it (the near, windward yarn solid; the far one faint through the cloth; green
	 * to starboard, red to port) and one onto the main's leech with its three ribbons. Each yarn reads the 3D ribbons' own
	 * rules (JibTelltaleState, LeechTelltaleState) over a third of the sail (SSailHud::TrimYarnState), so the panel, the
	 * sail and the verdict agree. A boat with no jib shows the luff of her main. UI Natural (Mode 1) draws only the two
	 * windows, a glimpse with no words; UI Helpful (Mode 0) sets them on a panel with a header and one plain line
	 * (SSailHud::TrimVerdict).
	 */
	class STrimView : public SLeafWidget
	{
	public:
		SLATE_BEGIN_ARGS(STrimView) : _bHelpful(true) {}
			SLATE_ARGUMENT(TWeakObjectPtr<APlayerController>, Player)
			SLATE_ARGUMENT(bool, bHelpful)
			SLATE_ATTRIBUTE(FText, Point)
			SLATE_ATTRIBUTE(SSailHud::FTrimVerdict, Verdict)
		SLATE_END_ARGS()
		void Construct(const FArguments& A) { Player = A._Player; bHelpful = A._bHelpful; Point = A._Point; Verdict = A._Verdict; ForceVolatile(true); }
		virtual FVector2D ComputeDesiredSize(float) const override
		{
			return bHelpful ? FVector2D(Pad * 2.f + JibW + Gap + MainW, HelpfulLayout().Height) : FVector2D(JibW + Gap + MainW + 2.f, WinH + 3.f);
		}
		virtual int32 OnPaint(const FPaintArgs&, const FGeometry& G, const FSlateRect&, FSlateWindowElementList& Out, int32 Layer, const FWidgetStyle&, bool) const override
		{
			const ASailboatPawn* Boat = Player.IsValid() ? Cast<ASailboatPawn>(Player->GetPawn()) : nullptr;
			if (!Boat) return Layer;
			const FBoatTelemetry& T = Boat->GetBoatModel().GetTelemetry();
			const bool bTied = Boat->IsTiedUp();
			const float Time = float(FPlatformTime::Seconds());
			const FVector2f S(G.GetLocalSize());
			const FHelpfulLayout Lay = HelpfulLayout();
			const FVector2f O = bHelpful ? FVector2f(Pad, Lay.WindowsTop) : FVector2f(0.f, 0.f);
			if (bHelpful)
			{
				const FLinearColor Bg = IsLow() ? PanelSolid : Panel;
				FSlateDrawElement::MakeBox(Out, Layer, G.ToPaintGeometry(), Rounded(Bg, RadiusCard, Line, 1.f), ESlateDrawEffect::None, NightCol(Bg));
				const FSlateFontInfo LabelFont = Font(EType::Label);
				const float LabelW = PaintText(Out, Layer + 1, G, TEXT("TELLTALES"), LabelFont, Muted, FVector2f(Pad, 10.f), 0.f);
				PaintText(Out, Layer + 1, G, Point.Get().ToString(), Font(EType::Small), Muted, FVector2f(S.X - Pad, 10.f), S.X - Pad * 2.f - LabelW - 12.f, true);
			}
			DrawJibWindow(Out, Layer + 1, G, O, T, bTied, Time);
			DrawMainWindow(Out, Layer + 1, G, O + FVector2f(JibW + Gap, 0.f), T, bTied, Time);
			if (bHelpful)
			{
				// Judged with the tip card, at the HUD's 10 Hz text rate (SSailHud::Refresh), so the two read the same moment.
				const SSailHud::FTrimVerdict V = Verdict.Get();
				const FLinearColor Tone = V.bNeutral ? Muted : V.bGood ? WindTrue : Warn;
				FSlateDrawElement::MakeBox(Out, Layer + 5, G.ToPaintGeometry(FVector2f(9.f, 9.f), FSlateLayoutTransform(FVector2f(Pad + 1.f, Lay.HeadTop + Lay.HeadH * 0.5f - 4.5f))), Rounded(Tone, 4.5f), ESlateDrawEffect::None, NightCol(Tone));
				PaintText(Out, Layer + 5, G, V.Head, Font(EType::Ui), Fg, FVector2f(Pad + 16.f, Lay.HeadTop), S.X - Pad * 2.f - 16.f);
				if (*V.Say) PaintText(Out, Layer + 5, G, V.Say, Font(EType::Small), Hex(0xC3D0D7), FVector2f(Pad, Lay.SayTop), S.X - Pad * 2.f);
			}
			return Layer + 6;
		}

	private:
		static constexpr float Pad = 16.f;
		static constexpr float JibW = 190.f;
		static constexpr float MainW = 70.f;
		static constexpr float Gap = 8.f;
		static constexpr float WinH = 90.f;

		/** UI Helpful's rows from the fonts' own line heights, so a bigger type scale or Settings > Text size moves them
		 *  down instead of overlapping: header, the windows, the headline, the line, and the panel's height. */
		struct FHelpfulLayout { float WindowsTop = 34.f, HeadTop = 132.f, HeadH = 24.f, SayTop = 158.f, Height = 196.f; };
		static float LineHeight(const FSlateFontInfo& F)
		{
			if (FSlateApplication::IsInitialized()) return float(FSlateApplication::Get().GetRenderer()->GetFontMeasureService()->GetMaxCharacterHeight(F));
			return float(F.Size) * 1.4f;
		}
		static FHelpfulLayout HelpfulLayout()
		{
			FHelpfulLayout L;
			L.WindowsTop = 10.f + LineHeight(Font(EType::Label)) + 6.f;
			L.HeadTop = L.WindowsTop + WinH + 8.f;
			L.HeadH = LineHeight(Font(EType::Ui));
			L.SayTop = L.HeadTop + L.HeadH + 1.f;
			L.Height = L.SayTop + LineHeight(Font(EType::Small)) + 10.f;
			return L;
		}

		/** How a yarn hangs: its first heading (radians, 0 = streaming aft, positive = down), the flutter toward the tail, the curl. */
		enum class EYarn : uint8 { Stream, Lift, Stall, Flutter, LeechCurl, Hang };
		static EYarn LuffYarn(ETelltaleState St)
		{
			return St == ETelltaleState::Lifting ? EYarn::Lift : St == ETelltaleState::Stalled ? EYarn::Stall : St == ETelltaleState::Fluttering ? EYarn::Flutter : EYarn::Stream;
		}
		static EYarn LeechYarn(ETelltaleState St)
		{
			return St == ETelltaleState::Stalled ? EYarn::LeechCurl : St == ETelltaleState::Fluttering ? EYarn::Flutter : EYarn::Stream;
		}

		/** One wool yarn from its patch: a chain of short segments whose heading flutters more toward the tail. */
		static void DrawYarn(FSlateWindowElementList& Out, int32 Layer, const FGeometry& G, FVector2f Root, float Len, EYarn Kind, float Sev, float Time, float Phase, const FLinearColor& Col, float Width)
		{
			float Base = 0.06f, Wob = 0.22f, Curl = 0.f, Speed = 13.f;
			switch (Kind)
			{
			case EYarn::Lift: Base = -1.25f * Sev; Wob = 0.85f; Curl = 2.f * Sev; Speed = 7.f; break;
			case EYarn::Stall: Base = 1.35f; Wob = 0.35f; Curl = 0.9f; Speed = 2.6f; break;
			case EYarn::Flutter: Base = 0.1f; Wob = 0.75f; Speed = 21.f; break;
			case EYarn::LeechCurl: Base = 0.35f; Wob = 0.25f; Curl = 2.6f; Speed = 2.4f; break;
			case EYarn::Hang: Base = 1.45f; Wob = 0.05f; Speed = 1.2f; break;
			default: break;
			}
			constexpr int32 N = 14;
			TArray<FVector2f> P;
			P.Reserve(N + 1);
			P.Add(Root);
			FVector2f At = Root;
			for (int32 K = 1; K <= N; ++K)
			{
				const float F = float(K) / N;
				const float H = Base + Wob * F * FMath::Sin(Time * Speed - K * 0.6f + Phase) + Curl * F * F * (0.7f + 0.5f * FMath::Sin(Time * Speed * 0.45f + Phase * 1.7f));
				At += FVector2f(FMath::Cos(H), FMath::Sin(H)) * (Len / N);
				P.Add(At);
			}
			FSlateDrawElement::MakeLines(Out, Layer, G.ToPaintGeometry(), P, ESlateDrawEffect::None, NightCol(Col), true, Width);
		}

		/** Text at At (its top left, or its top right when bRight), shrunk to fit MaxW when MaxW > 0. Returns its width. */
		static float PaintText(FSlateWindowElementList& Out, int32 Layer, const FGeometry& G, const FString& Str, FSlateFontInfo F, const FLinearColor& Col, FVector2f At, float MaxW, bool bRight = false)
		{
			float W = 0.f;
			if (FSlateApplication::IsInitialized())
			{
				const TSharedRef<FSlateFontMeasure> Measure = FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
				W = float(Measure->Measure(Str, F).X);
				if (MaxW > 0.f && W > MaxW)
				{
					F.Size = static_cast<decltype(F.Size)>(FMath::Max(8.f, float(F.Size) * MaxW / W));
					W = float(Measure->Measure(Str, F).X);
				}
			}
			const FVector2f Pos = bRight ? FVector2f(At.X - W, At.Y) : At;
			FSlateDrawElement::MakeText(Out, Layer, G.ToPaintGeometry(FVector2f(FMath::Max(W, 1.f) + 4.f, 30.f), FSlateLayoutTransform(Pos)), Str, F, ESlateDrawEffect::None, NightCol(Col));
			return W;
		}

		void Frame(FSlateWindowElementList& Out, int32 Layer, const FGeometry& G, FVector2f At, float W) const
		{
			// A hairline round the window. Lines, not a box: MakeBox paints its tint as the fill (CLAUDE.md), and a rounded
			// outline brush tinted white covered the whole window (#712's first Mac stills).
			const FVector2f A = At + FVector2f(0.5f, 0.5f), B = At + FVector2f(W - 0.5f, WinH - 0.5f);
			FSlateDrawElement::MakeLines(Out, Layer, G.ToPaintGeometry(), { A, FVector2f(B.X, A.Y), B, FVector2f(A.X, B.Y), A }, ESlateDrawEffect::None, NightCol(Hex(0x000000, 0.35f)), true, 1.f);
		}
		void Shadow(FSlateWindowElementList& Out, int32 Layer, const FGeometry& G, FVector2f At, float W) const
		{
			// UI Natural has no panel: a soft drop shadow keeps the windows off a bright sky.
			if (!bHelpful) FSlateDrawElement::MakeBox(Out, Layer, G.ToPaintGeometry(FVector2f(W, WinH), FSlateLayoutTransform(At + FVector2f(2.f, 3.f))), Rounded(Hex(0x000000, 0.35f), 4.f), ESlateDrawEffect::None, NightCol(Hex(0x000000, 0.35f)));
		}

		/** Sailcloth, lit from the cockpit: a shade at the luff tape, a little darker toward the far edge. */
		static void Cloth(FSlateWindowElementList& Out, int32 Layer, const FGeometry& G, FVector2f At, FVector2f Size)
		{
			TArray<FSlateGradientStop> Stops;
			Stops.Add(FSlateGradientStop(FVector2f(0.f, 0.f), NightDim(Hex(0xCFD6D5), 0.3f)));
			Stops.Add(FSlateGradientStop(FVector2f(Size.X * 0.08f, 0.f), NightDim(Hex(0xEEF0EC), 0.3f)));
			Stops.Add(FSlateGradientStop(FVector2f(Size.X * 0.7f, 0.f), NightDim(Hex(0xE6E9E5), 0.3f)));
			Stops.Add(FSlateGradientStop(FVector2f(Size.X, 0.f), NightDim(Hex(0xD6DCDA), 0.3f)));
			FSlateDrawElement::MakeGradient(Out, Layer, G.ToPaintGeometry(Size, FSlateLayoutTransform(At)), Stops, Orient_Vertical);
		}

		void DrawJibWindow(FSlateWindowElementList& Out, int32 Layer, const FGeometry& G, FVector2f At, const FBoatTelemetry& T, bool bTied, float Time) const
		{
			Shadow(Out, Layer, G, At, JibW);
			Out.PushClip(FSlateClippingZone(G.ToPaintGeometry(FVector2f(JibW, WinH), FSlateLayoutTransform(At))));
			Cloth(Out, Layer + 1, G, At, FVector2f(JibW, WinH));
			for (int32 I = 0; I < 3; ++I)   // panel seams
			{
				FSlateDrawElement::MakeLines(Out, Layer + 1, G.ToPaintGeometry(), { At + FVector2f(40.f + I * 70.f, 0.f), At + FVector2f(20.f + I * 70.f, WinH) }, ESlateDrawEffect::None, NightCol(Hex(0x3C464B, 0.1f)), true, 1.f);
			}
			FSlateDrawElement::MakeBox(Out, Layer + 1, G.ToPaintGeometry(FVector2f(9.f, WinH), FSlateLayoutTransform(At)), White(), ESlateDrawEffect::None, NightDim(Hex(0xBCC4C5), 0.3f));   // luff tape
			FSlateDrawElement::MakeLines(Out, Layer + 2, G.ToPaintGeometry(), { At + FVector2f(4.f, 0.f), At + FVector2f(4.f, WinH) }, ESlateDrawEffect::None, NightCol(Hex(0x56636A)), true, 2.f);   // forestay
			// A cat rig (Sunfish, ILCA) shows her one sail's luff here and its leech in the other window.
			if (bHelpful) PaintText(Out, Layer + 2, G, T.NumJibStrips > 0 ? TEXT("JIB") : TEXT("LUFF"), Font(EType::Label), Hex(0x7F8B90), At + FVector2f(JibW - 8.f, 4.f), 0.f, true);
			// The windward face is the side the wind comes from: green to starboard, red to port, as on a real boat.
			const bool bStbdWindward = T.ApparentWindAngle >= 0.0;
			const FLinearColor Near = bStbdWindward ? Starboard : Port, Far = bStbdWindward ? Port : Starboard;
			const bool bJib = T.NumJibStrips > 0;
			const FSailStripState* Strips = bJib ? T.JibStrips : T.MainStrips;
			const int32 N = bJib ? T.NumJibStrips : T.NumMainStrips;
			for (int32 K = 0; K < 3 && N > 0; ++K)
			{
				const int32 Band = 2 - K;   // top first, as you look up the luff
				const EYarn Win = bTied ? EYarn::Hang : LuffYarn(SSailHud::TrimYarnState(Strips, N, Band, SSailHud::ETrimYarn::LuffWindward));
				const EYarn Lee = bTied ? EYarn::Hang : LuffYarn(SSailHud::TrimYarnState(Strips, N, Band, SSailHud::ETrimYarn::LuffLeeward));
				const FVector2f Root = At + FVector2f(44.f, 15.f + 30.f * K);
				// Hanging at the dock a full-length yarn would run into the one below (#712's 130% still): it hangs short.
				const float Len = bTied ? 24.f : 62.f;
				const float Ph = K * 1.3f;
				// The far yarn, seen through the cloth: a soft wide shadow and a faint line.
				DrawYarn(Out, Layer + 2, G, Root + FVector2f(0.f, 1.f), Len, Lee, 1.f, Time, Ph + 1.1f, Far.CopyWithNewOpacity(0.14f), 6.f);
				DrawYarn(Out, Layer + 2, G, Root + FVector2f(0.f, 1.f), Len, Lee, 1.f, Time, Ph + 1.1f, Far.CopyWithNewOpacity(0.4f), 2.6f);
				// The near yarn: solid wool with a little shadow on the cloth.
				const float Sev = 1.f - 0.08f * K;
				DrawYarn(Out, Layer + 3, G, Root, Len, Win, Sev, Time, Ph, Hex(0x000000, 0.18f), 4.6f);
				DrawYarn(Out, Layer + 3, G, Root, Len, Win, Sev, Time, Ph, Near, 3.2f);
				FSlateDrawElement::MakeBox(Out, Layer + 4, G.ToPaintGeometry(FVector2f(7.f, 7.f), FSlateLayoutTransform(Root - FVector2f(3.5f, 3.5f))), Rounded(Hex(0xF7F8F5), 3.5f, Hex(0x000000, 0.22f), 1.f), ESlateDrawEffect::None, NightCol(Hex(0xF7F8F5)));
			}
			Out.PopClip();
			Frame(Out, Layer + 4, G, At, JibW);
		}

		void DrawMainWindow(FSlateWindowElementList& Out, int32 Layer, const FGeometry& G, FVector2f At, const FBoatTelemetry& T, bool bTied, float Time) const
		{
			Shadow(Out, Layer, G, At, MainW);
			Out.PushClip(FSlateClippingZone(G.ToPaintGeometry(FVector2f(MainW, WinH), FSlateLayoutTransform(At))));
			TArray<FSlateGradientStop> Sky;   // looking aft past the leech
			Sky.Add(FSlateGradientStop(FVector2f(0.f, 0.f), NightDim(Hex(0xA8C3D6), 0.3f)));
			Sky.Add(FSlateGradientStop(FVector2f(0.f, WinH), NightDim(Hex(0xC9D8E2), 0.3f)));
			FSlateDrawElement::MakeGradient(Out, Layer + 1, G.ToPaintGeometry(FVector2f(MainW, WinH), FSlateLayoutTransform(At)), Sky, Orient_Horizontal);
			// The main, out to its leech: a gentle curve (the roach), drawn in thin bands.
			auto LeechX = [](float F) { return MainW * 0.42f + FMath::Sin(F * UE_PI) * 8.f; };
			constexpr int32 Bands = 30;
			for (int32 B = 0; B < Bands; ++B)
			{
				const float F = (B + 0.5f) / Bands, H = WinH / Bands;
				FSlateDrawElement::MakeBox(Out, Layer + 1, G.ToPaintGeometry(FVector2f(LeechX(F), H + 0.5f), FSlateLayoutTransform(At + FVector2f(0.f, B * H))), White(), ESlateDrawEffect::None, NightDim(Hex(0xE4E7E3), 0.3f));
			}
			TArray<FVector2f> Leech;
			for (int32 I = 0; I <= 10; ++I) Leech.Add(At + FVector2f(LeechX(I / 10.f) - 1.f, WinH * I / 10.f));
			FSlateDrawElement::MakeLines(Out, Layer + 2, G.ToPaintGeometry(), Leech, ESlateDrawEffect::None, NightDim(Hex(0xAAB3B5), 0.3f), true, 2.f);
			// Three ribbons at the battens, one for each third of the leech, top first; the top one clear of the label.
			for (int32 K = 0; K < 3 && T.NumMainStrips > 0; ++K)
			{
				const float F = 0.34f + 0.23f * K;
				const EYarn Kind = bTied ? EYarn::Hang : LeechYarn(SSailHud::TrimYarnState(T.MainStrips, T.NumMainStrips, 2 - K, SSailHud::ETrimYarn::Leech));
				DrawYarn(Out, Layer + 3, G, At + FVector2f(LeechX(F), WinH * F), bTied ? 16.f : 28.f, Kind, 1.f, Time, 2.2f * K + 0.7f, Hex(0xC8281E), 2.6f);
			}
			Out.PopClip();
			if (bHelpful) PaintText(Out, Layer + 4, G, T.NumJibStrips > 0 ? TEXT("MAIN") : TEXT("LEECH"), Font(EType::Label), Hex(0x4B5D68), At + FVector2f(MainW - 6.f, 4.f), 0.f, true);
			Frame(Out, Layer + 4, G, At, MainW);
		}

		TWeakObjectPtr<APlayerController> Player;
		bool bHelpful = true;
		TAttribute<FText> Point;
		TAttribute<SSailHud::FTrimVerdict> Verdict;
	};

	TSharedRef<SWidget> Field(const FString& Label, TAttribute<FText> Value)
	{
		return SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(Label, EType::Label, Muted) ]
			+ SVerticalBox::Slot().AutoHeight()[ TextAttr(Value, EType::Value, FSlateColor(Fg)) ];
	}

	TAttribute<FText> Attr(const FText& Ref) { return TAttribute<FText>::CreateLambda([&Ref]() { return Ref; }); }
	TAttribute<FSlateColor> ColorAttr(const FLinearColor& Ref) { return NightLift(TAttribute<FSlateColor>::CreateLambda([&Ref]() { return FSlateColor(Ref); })); }

	/** Settings > Display > HUD size as a scale (0.85 to 1.3); -SailingHudScale=<percent> overrides it for layout stills
	 *  (docs/hud-layout/). The argument is read once per command line (it is swapped by bench lists). */
	float HudScaleNow()
	{
		static uint32 Gen = MAX_uint32;
		static int32 ArgPercent = 0;
		if (Gen != SailingArgs::Generation())
		{
			Gen = SailingArgs::Generation();
			FString V;
			ArgPercent = SailingArgs::LastValue(SailingArgs::Dev(), TEXT("SailingHudScale="), V) ? FCString::Atoi(*V) : 0;
		}
		const int32 Percent = ArgPercent > 0 ? ArgPercent : USailingSettings::Get()->HudScale;
		return FMath::Clamp(Percent, 85, 130) / 100.f;
	}

	/** Message text over the scene: the HUD's text with a dark drop shadow, so a letter still reads where the card's edge
	 *  meets bright water or sky. */
	TSharedRef<SWidget> ShadowText(TAttribute<FText> S, EType Type, TAttribute<FSlateColor> Color, bool bWrap)
	{
		return SNew(STextBlock).Text(S).Font(Font(Type)).ColorAndOpacity(NightLift(Color)).AutoWrapText(bWrap)
			.ShadowOffset(FVector2D(1.5, 1.5)).ShadowColorAndOpacity(FLinearColor(0.f, 0.f, 0.f, 0.85f))
			.LineHeightPercentage(Type == EType::Body || Type == EType::Small ? 1.3f : 1.f);
	}

	/** A message card (docs/hud-layout/): near-opaque ink (the panels' 0.8 let a bright sky or whitecaps through the
	 *  letters), a light rim and a 6 px edge in the message's colour. */
	TSharedRef<SWidget> MessageCard(TFunction<FLinearColor()> EdgeColor, TSharedRef<SWidget> Content)
	{
		return SNew(SHorizontalBox)
			+ SHorizontalBox::Slot().AutoWidth()[ SNew(SBox).WidthOverride(6.f)[ SNew(SBorder).BorderImage_Lambda([EdgeColor]() { return Rounded(EdgeColor(), 2.f); }) ] ]
			+ SHorizontalBox::Slot().FillWidth(1.f)
			[
				SNew(SBorder).BorderImage(Rounded(Ink.CopyWithNewOpacity(0.92f), 4.f, Line, 1.f)).Padding(FMargin(16.f, 10.f))[ Content ]
			];
	}

	/** The tip card's title for a learning tip's ASA topic. */
	FString LearningTopicName(const FString& Topic)
	{
		static const TMap<FString, FString> Names = { { TEXT("sail"), TEXT("Sail handling") }, { TEXT("trim"), TEXT("Trim") }, { TEXT("rules"), TEXT("Rules of the road") },
			{ TEXT("safety"), TEXT("Safety") }, { TEXT("dock"), TEXT("Docking") }, { TEXT("weather"), TEXT("Weather") }, { TEXT("nav"), TEXT("Navigation") },
			{ TEXT("knots"), TEXT("Knots") }, { TEXT("lights"), TEXT("Lights") }, { TEXT("parts"), TEXT("The boat") }, { TEXT("aton"), TEXT("Aids to navigation") } };
		const FString* N = Names.Find(Topic);
		return N ? *N : FString(TEXT("Coach"));
	}

	/** The live key for a tip: the controller's binding while the player is on the pad (SailingBindings::Label). */
	FString KeyName(FName Action, bool bNegative) { return SailingBindings::Label(Action, bNegative, SailUI::UsingGamepad()); }
}

void SSailHud::Construct(const FArguments& A)
{
	using namespace SailUI;
	using namespace SailHudImpl;
	Player = A._Player;
	RegisterInputTracker();
	SailUI::PreloadFonts();   // before the first card shows mid-session (an 84 ms first-use load)
	// Stills of each HUD mode (docs/trim-panel/): -SailingHudMode=0 Full (UI Helpful), 1 Minimal (UI Natural), 2 Off.
	if (int32 Forced = 0; FParse::Value(FCommandLine::Get(), TEXT("-SailingHudMode="), Forced)) Mode = FMath::Clamp(Forced, 0, 2);
	UTexture2D* Tex = SailUI::KeptTexture(SailCatalog::MiniMap(USailingSettings::Get()->World).Texture);
	MapBrush = MakeShared<FSlateBrush>();
	if (Tex) { MapBrush->SetResourceObject(Tex); MapBrush->ImageSize = FVector2D(Tex->GetSizeX(), Tex->GetSizeY()); }
	auto Full = [](){ return Mode == 0 ? EVisibility::HitTestInvisible : EVisibility::Collapsed; };
	auto NotOff = [](){ return Mode < 2 ? EVisibility::HitTestInvisible : EVisibility::Collapsed; };
	auto Natural = [](){ return Mode == 1 ? EVisibility::HitTestInvisible : EVisibility::Collapsed; };
	// Shown while the right-hand column's fit level is at most Level (RightFit: lines dropped whole when room runs out).
	auto UpTo = [this](int32 Level) { return [this, Level]() { return RightFit <= Level ? EVisibility::HitTestInvisible : EVisibility::Collapsed; }; };
	auto Heading = [this]() { const ASailboatPawn* P = Pawn(); return P ? float(P->GetHeadingTrueDeg()) : 0.f; };
	auto WindFrom = [this]() { const ASailboatPawn* P = Pawn(); const ASailingGameMode* GM = P ? P->GetWorld()->GetAuthGameMode<ASailingGameMode>() : nullptr; return GM ? float(GM->GetWeatherState().Wind.FromDegrees) : 0.f; };
	auto Awa = [this]() { const ASailboatPawn* P = Pawn(); return P ? float(FMath::RadiansToDegrees(P->GetBoatModel().GetTelemetry().ApparentWindAngle)) : 0.f; };
	auto Twa = [this]() { const ASailboatPawn* P = Pawn(); return P ? float(FMath::RadiansToDegrees(P->GetBoatModel().GetTelemetry().TrueWindAngle)) : 0.f; };
	// Easy mode's wider no-go cue, from the sim (FEasyAssists, NoGoCueFor), not a HUD guess.
	auto NoGo = [this]() { const ASailboatPawn* P = Pawn(); return P ? float(P->GetEasyAssists().NoGoDeg()) : float(Sailing::FEasyAssists::kRealisticNoGoDeg); };
	auto Cue = [this]() { const ASailboatPawn* P = Pawn(); return P ? int32(Sailing::NoGoCueFor(P->GetBoatModel().GetTelemetry(), P->GetEasyAssists())) : 0; };
	auto Wide = [this]() { const ASailboatPawn* P = Pawn(); return P && P->GetEasyAssists().bEnabled; };
	// UI overhaul phase 4: UI Natural is box-free. The instruments lose their panels, labels and second lines; what is
	// left (the dial on its own round face, the speed, the depth, the compass tape) reads by a drop shadow.
	auto Bare = []() { return Mode == 1; };
	auto HudPanel = [](TSharedRef<SWidget> Content, const FMargin& Pad) -> TSharedRef<SWidget>
	{
		return SNew(SBorder).BorderImage_Lambda([]() { return Mode == 1 ? Rounded(FLinearColor::Transparent, 0.f) : Rounded(IsLow() ? PanelSolid : Panel, RadiusCard, Line, 1.f); }).Padding(Pad)[ Content ];
	};
	auto FullOnly = [Full](TSharedRef<SWidget> W) -> TSharedRef<SWidget> { return SNew(SBox).Visibility_Lambda(Full)[ W ]; };
	const float M = HudMargin;
	ChildSlot
	[
		// Perf 1 fix 9: the HUD is cached and repainted only where something changed (its text changes at 10 Hz); the
		// instruments drawn from the live boat (compass, wind dial, minimap, trim) are volatile and drawn every frame.
		SNew(SInvalidationPanel)
		[
		// Settings > Display > HUD size scales every panel around its anchor.
		SNew(SDPIScaler).DPIScale_Lambda([]() { return HudScaleNow(); })
		[
		// The night palette (docs/ui-overhaul/, Phase 6): after dark every panel and word is tinted red, so the eye keeps
		// its night sight. The tint sits inside the invalidation panel, so a change repaints the cached HUD.
		SNew(SBorder).BorderImage(FStyleDefaults::GetNoBrush()).Padding(0.f).Visibility(EVisibility::SelfHitTestInvisible)
		.ColorAndOpacity_Lambda([]() { return SSailHud::NightColor(FLinearColor::White, NightHud); })
		[
		SNew(SOverlay).Visibility_Lambda([this]()
		{
			const ASailboatPawn* P = Pawn();
			const bool bHide = !P || P->IsCaptureMode() || P->IsPhotoMode() || P->IsWatching() || P->IsChartOpen() || P->IsLogOpen() || P->IsKeysOpen()
				|| P->IsMenuOpen() || P->IsControlsCardOpen() || P->IsHeldByUI() || !USailingSettings::Get()->bShowHud;
			const ASailingHUD* Hud = Player.IsValid() ? Cast<ASailingHUD>(Player->GetHUD()) : nullptr;
			if (Hud && Hud->IsFrontEndOpen()) return EVisibility::Collapsed;   // pause and the menus cover the screen
			return bHide ? EVisibility::Collapsed : EVisibility::HitTestInvisible;
		})
		// The left-hand column, top to bottom: the environment strip, the tip card and the rules callout in the room above the
		// instruments (they condense, then clip, rather than run into them: LeftPanelsRoom, bCompactLeft); the instruments at
		// the bottom (Bean Nov 15: where the minimap was), so the bottom centre stays clear for the boat.
		+ SOverlay::Slot().HAlign(HAlign_Left).VAlign(VAlign_Fill).Padding(M)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().FillHeight(1.f).HAlign(HAlign_Left)
			[
			SAssignNew(LeftPanelsRoom, SBox).VAlign(VAlign_Top)
			[
			SAssignNew(LeftPanels, SBox).Clipping(EWidgetClipping::ClipToBounds)
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
							+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 8.f, 0.f, 0.f)[ SNew(SBox).Visibility_Lambda([this]() { return bCompactLeft ? EVisibility::Collapsed : EVisibility::HitTestInvisible; })[ SailUI::Text(TEXT("Hide tips with H · Tips off in Game mode"), EType::Small, Dim) ] ],
							FMargin(16.f, 12.f), 4.f)
					]
				]
			]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 12.f, 0.f, 0.f)
			[
				SNew(SBox).WidthOverride(400.f).Visibility_Lambda([this]() { return bCoach && Mode < 2 ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
				[
					SNew(SHorizontalBox)
					+ SHorizontalBox::Slot().AutoWidth()[ SNew(SBox).WidthOverride(4.f)[ SNew(SBorder).BorderImage_Lambda([this]() { return Rounded(CoachRoleColor, 2.f); }) ] ]
					+ SHorizontalBox::Slot().FillWidth(1.f)
					[
						PanelBox(SNew(SVerticalBox)
							+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(TEXT("Rules of the road"), EType::Eyebrow, Accent) ]
							+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 6.f, 0.f, 2.f)[ TextAttr(Attr(CoachRole), EType::Ui, ColorAttr(CoachRoleColor), true) ]
							+ SVerticalBox::Slot().AutoHeight()[ TextAttr(Attr(CoachWho), EType::Small, FSlateColor(Fg), true) ]
							+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 4.f, 0.f, 0.f)[ TextAttr(Attr(CoachAction), EType::Small, FSlateColor(Fg), true) ]
							+ SVerticalBox::Slot().AutoHeight()[ SNew(SBox).Visibility_Lambda([this]() { return bCompactLeft ? EVisibility::Collapsed : EVisibility::HitTestInvisible; })[ TextAttr(Attr(CoachReason), EType::Small, FSlateColor(Muted), true) ] ]
							+ SVerticalBox::Slot().AutoHeight()[ SNew(SBox).Visibility_Lambda([this]() { return CoachCpa.IsEmpty() ? EVisibility::Collapsed : EVisibility::HitTestInvisible; })[ TextAttr(Attr(CoachCpa), EType::Small, ColorAttr(CoachCpaColor), true) ] ],
							FMargin(16.f, 10.f), 4.f)
					]
				]
			]
			]
			]
			]
			// Bottom of the column: the apparent wind dial, then speed over depth.
			+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Left).Padding(0.f, 12.f, 0.f, 0.f)
			[
				SNew(SHorizontalBox).Visibility_Lambda(NotOff)
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Fill).Padding(0.f, 0.f, 10.f, 0.f)
				[
					// The panel stretches to the full height of the speed and depth stack beside it (Bean Nov 24); its contents stay centred.
					HudPanel(SNew(SBox).VAlign(VAlign_Center)[ SNew(SVerticalBox)
						+ SVerticalBox::Slot().AutoHeight()[ SNew(SBox).WidthOverride(180.f).HeightOverride(170.f)[ SNew(SWindDialHud).Awa_Lambda(Awa).Twa_Lambda(Twa).NoGo_Lambda(NoGo).Cue_Lambda(Cue).Wide_Lambda(Wide).Bare_Lambda(Bare) ] ]
						+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)[ ShadowText(TAttribute<FText>::CreateLambda([this]() { return AwaText; }), EType::Value, FSlateColor(Fg), false) ]
						+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)[ FullOnly(TextAttr(TAttribute<FText>::CreateLambda([this]() { return AwsText; }), EType::Label, FSlateColor(Muted))) ] ], FMargin(10.f, 8.f))
				]
				+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Bottom)
				[
					SNew(SVerticalBox)
					+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 0.f, 0.f, 10.f)
					[
						SNew(SBox).WidthOverride(200.f)
						[
							HudPanel(SNew(SVerticalBox)
								+ SVerticalBox::Slot().AutoHeight()[ FullOnly(SailUI::Text(TEXT("Speed"), EType::Label, Muted)) ]
								+ SVerticalBox::Slot().AutoHeight()
								[
									SNew(SHorizontalBox)
									+ SHorizontalBox::Slot().AutoWidth()[ ShadowText(TAttribute<FText>::CreateLambda([this]() { return SpeedText; }), EType::InstrumentBig, FSlateColor(Fg), false) ]
									+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Bottom).Padding(6.f, 0.f, 0.f, 10.f)[ ShadowText(Attr(SpeedUnitText), EType::Small, TAttribute<FSlateColor>::CreateLambda([]() { return FSlateColor(Mode == 1 ? Fg : Muted); }), false) ]
								]
								+ SVerticalBox::Slot().AutoHeight()[ FullOnly(TextAttr(TAttribute<FText>::CreateLambda([this]() { return SpeedSub; }), EType::Small, FSlateColor(Muted))) ], FMargin(16.f, 12.f))
						]
					]
					+ SVerticalBox::Slot().AutoHeight()
					[
						SNew(SBox).WidthOverride(200.f)
						[
							SNew(SBorder).BorderImage_Lambda([this]() { return Mode == 1 && !bShallow ? Rounded(FLinearColor::Transparent, 0.f) : Rounded(IsLow() ? PanelSolid : Panel, RadiusCard, bShallow ? Warn : Line, bShallow ? 2.f : 1.f); }).Padding(FMargin(16.f, 12.f))
							[
								SNew(SVerticalBox)
								+ SVerticalBox::Slot().AutoHeight()[ FullOnly(SailUI::Text(TEXT("Depth"), EType::Label, Muted)) ]
								+ SVerticalBox::Slot().AutoHeight()
								[
									SNew(SHorizontalBox)
									+ SHorizontalBox::Slot().AutoWidth()[ ShadowText(TAttribute<FText>::CreateLambda([this]() { return DepthText; }), EType::InstrumentBig, TAttribute<FSlateColor>::CreateLambda([this]() { return FSlateColor(bShallow ? Warn : Fg); }), false) ]
									+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Bottom).Padding(6.f, 0.f, 0.f, 10.f)[ ShadowText(Attr(DepthUnitText), EType::Small, TAttribute<FSlateColor>::CreateLambda([]() { return FSlateColor(Mode == 1 ? Fg : Muted); }), false) ]
								]
								+ SVerticalBox::Slot().AutoHeight()[ FullOnly(TextAttr(TAttribute<FText>::CreateLambda([this]() { return DepthSub; }), EType::Small, FSlateColor(Muted))) ]
							]
						]
					]
				]
			]
		]
		// Top-centre: the compass tape and heading (the toasts moved to the message stack, centre right).
		// (Centred on the screen and padded clear of the strip and the right-hand panels: it narrows on a 4:3 screen rather than
		// overlapping them.)
		+ SOverlay::Slot().HAlign(HAlign_Center).VAlign(VAlign_Top).Padding(FMargin(M + 530.f, M, M + 530.f, M))
		[
			SNew(SVerticalBox).Visibility_Lambda(NotOff)
			+ SVerticalBox::Slot().AutoHeight()[ SNew(SBox).MaxDesiredWidth(650.f).MinDesiredWidth(260.f).HeightOverride(50.f)[ SNew(SCompassTape).Heading_Lambda(Heading).WindFrom_Lambda(WindFrom).Bare_Lambda(Bare) ] ]
			+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0.f, 6.f)[ ShadowText(TAttribute<FText>::CreateLambda([this]() { return HeadingText; }), EType::Value, FSlateColor(Fg), false) ]
		]
		// The wrist compass (Phase 8): with the interface off, a glance at the wrist, bottom left where the instruments were.
		+ SOverlay::Slot().HAlign(HAlign_Left).VAlign(VAlign_Bottom).Padding(M)
		[
			SNew(SBox).Visibility_Lambda([this]() { const ASailboatPawn* P = Pawn(); return Mode == 2 && P && P->IsWristUp() ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
			[ SNew(SWristCompass).Player(Player) ]
		]
		// The right-hand column, top to bottom (Bean Nov 15: the minimap moved here from the bottom left): the minimap in the
		// corner; the drill or race panel and the coast's navigation panel in the room left between it and the sail trim panel
		// (they shed whole lines, then whole panels, rather than run under it: RightPanelsRoom, RightFit); sail trim and key hints at
		// the bottom.
		+ SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Fill).Padding(M)
		[
			SNew(SVerticalBox)
			+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Right).Padding(0.f, 0.f, 0.f, 10.f)
			[ SNew(SBox).WidthOverride(210.f).HeightOverride(210.f).Visibility_Lambda(Full)[ SNew(SMiniMap).Player(Player).Map(MapBrush) ] ]
			+ SVerticalBox::Slot().FillHeight(1.f).HAlign(HAlign_Right)
			[
			SAssignNew(RightPanelsRoom, SBox).VAlign(VAlign_Top)
			[
			SAssignNew(RightPanels, SBox).Clipping(EWidgetClipping::ClipToBounds)
			[
			SNew(SVerticalBox).Visibility_Lambda(NotOff)
			+ SVerticalBox::Slot().AutoHeight()
			[
				SNew(SBox).WidthOverride(RightColumnWidth).Visibility_Lambda([this]() { return bDrill ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
				[
					PanelBox(SNew(SVerticalBox)
						+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(TEXT("Drill"), EType::Eyebrow, Accent) ]
						+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 4.f, 0.f, 8.f)[ TextAttr(Attr(DrillTitle), EType::CardTitleS, FSlateColor(Fg)) ]
						+ SVerticalBox::Slot().AutoHeight()[ SNew(SBox).Visibility_Lambda(UpTo(5))[ SAssignNew(DrillList, SVerticalBox) ] ]
						+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 8.f, 0.f, 0.f)[ SNew(SBox).Visibility_Lambda([this]() { return DrillFooter.IsEmpty() ? EVisibility::Collapsed : EVisibility::HitTestInvisible; })[ TextAttr(Attr(DrillFooter), EType::Small, FSlateColor(Muted), true) ] ],
						FMargin(18.f, 14.f))
				]
			]
			+ SVerticalBox::Slot().AutoHeight()
			[
				SNew(SBox).WidthOverride(RightColumnWidth).Visibility_Lambda([this]() { return bRace ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
				[
					PanelBox(SNew(SVerticalBox)
						+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(TEXT("Race"), EType::Eyebrow, Accent) ]
						+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 4.f, 0.f, 8.f)[ TextAttr(Attr(RaceHead), EType::CardTitleS, ColorAttr(RaceHeadColor)) ]
						+ SVerticalBox::Slot().AutoHeight()[ SNew(SBox).Visibility_Lambda(UpTo(6))[ TextAttr(Attr(RaceTask), EType::Ui, ColorAttr(RaceTaskColor), true) ] ]
						+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 4.f, 0.f, 0.f)[ SNew(SBox).Visibility_Lambda(UpTo(3))[ TextAttr(Attr(RaceLine), EType::Small, ColorAttr(RaceLineColor), true) ] ]
						+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 8.f, 0.f, 0.f)[ SNew(SBox).Visibility_Lambda([this]() { return RaceResults.IsEmpty() || Fit(4) ? EVisibility::Collapsed : EVisibility::HitTestInvisible; })[ TextAttr(Attr(RaceResults), EType::Small, FSlateColor(Fg), true) ] ]
						+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 10.f, 0.f, 0.f)[ SNew(SBox).Visibility_Lambda([this]() { return ScoreText.IsEmpty() || Fit(6) ? EVisibility::Collapsed : EVisibility::HitTestInvisible; })[ TextAttr(Attr(ScoreText), EType::Small, ColorAttr(ScoreColor), true) ] ],
						FMargin(18.f, 14.f))
				]
			]
			+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 12.f, 0.f, 0.f)
			[
				SNew(SBox).WidthOverride(RightColumnWidth).Visibility_Lambda([this]() { return bNav && Mode == 0 && !Fit(5) ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
				[
					PanelBox(SNew(SVerticalBox)
						+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(TEXT("Navigation"), EType::Eyebrow, Accent) ]
						+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 6.f, 0.f, 0.f)[ SNew(SBox).Visibility_Lambda(UpTo(3))[ TextAttr(Attr(NavText), EType::Small, FSlateColor(Fg), true) ] ]
						+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 6.f, 0.f, 0.f)[ SNew(SBox).Visibility_Lambda([this]() { return NextText.IsEmpty() ? EVisibility::Collapsed : EVisibility::HitTestInvisible; })[ TextAttr(Attr(NextText), EType::Ui, FSlateColor(Accent), true) ] ],
						FMargin(18.f, 14.f))
				]
			]
			]
			]
			]
			// Bottom of the column: sail trim and key hints. The trim panel follows the UI mode (docs/trim-panel/): UI Helpful
			// draws the telltale windows with a header and one plain line, UI Natural the windows alone, UI Off nothing.
			+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Right).Padding(0.f, 10.f, 0.f, 0.f)
			[
				SNew(SVerticalBox).Visibility_Lambda(NotOff)
				+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Right)
				[ SNew(STrimView).Player(Player).bHelpful(true).Point(TAttribute<FText>::CreateLambda([this]() { return PointText; })).Verdict_Lambda([this]() { return TrimShown; }).Visibility_Lambda(Full) ]
				+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Right)
				[ SNew(STrimView).Player(Player).bHelpful(false).Visibility_Lambda(Natural) ]
				+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Right).Padding(0.f, 10.f, 0.f, 0.f)
				[ SNew(SBox).Visibility_Lambda(Full)[ TextAttr(TAttribute<FText>::CreateLambda([this]() { return HintsText; }), EType::Small, FSlateColor(Muted)) ] ]
			]
		]
		// Centre-right: the messages (Bean Nov 15: easier to read over the scene, centre right). The captain's call, toasts,
		// rules points, signals heard and sound captions, each on a solid card, stacked from the screen's middle; left of the
		// right-hand panels when they show, and kept right of the boat where the screen is wide enough.
		+ SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Center)
			.Padding(TAttribute<FMargin>::CreateLambda([this, M]() { return FMargin(M, M, M + (RightPanelsShown() ? RightColumnWidth + MessageGap : 0.f), M); }))
		[
			SNew(SBox).WidthOverride_Lambda([this]() { return FOptionalSize(MessageWidthFor(LayoutWidth, RightPanelsShown())); })
			[
				SNew(SVerticalBox)
				// A ship's orders panel (docs/ship-orders/): while it is open, in every HUD mode (it is a menu the player opened).
				+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 0.f, 0.f, 10.f)
				[
					SNew(SBox).Visibility_Lambda([this]() { const ASailboatPawn* P = Pawn(); return P && P->GetShipOrders().IsOpen() ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
					[
						MessageCard([]() { return Accent; }, SNew(SVerticalBox)
							+ SVerticalBox::Slot().AutoHeight()[ ShadowText(TAttribute<FText>::CreateLambda([this]() { const ASailboatPawn* P = Pawn(); return FText::FromString(P ? P->GetOrdersPanelText(0) : FString()); }), EType::Eyebrow, FSlateColor(Accent), false) ]
							+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 6.f, 0.f, 6.f)[ ShadowText(TAttribute<FText>::CreateLambda([this]() { const ASailboatPawn* P = Pawn(); return FText::FromString(P ? P->GetOrdersPanelText(1) : FString()); }), EType::Ui, FSlateColor(Fg), false) ]
							+ SVerticalBox::Slot().AutoHeight()[ ShadowText(TAttribute<FText>::CreateLambda([this]() { const ASailboatPawn* P = Pawn(); return FText::FromString(P ? P->GetOrdersPanelText(2) : FString()); }), EType::Small, FSlateColor(Muted), true) ])
					]
				]
				// Prologue step 1: the captain's call; shown in every HUD mode (it is the scene).
				+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 0.f, 0.f, 10.f)
				[
					SNew(SBox).Visibility_Lambda([this]() { return bCaptain ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
					[
						MessageCard([]() { return Warn; }, SNew(SVerticalBox)
							+ SVerticalBox::Slot().AutoHeight()
							[
								SNew(SHorizontalBox)
								+ SHorizontalBox::Slot().FillWidth(1.f)[ ShadowText(Attr(CaptainWho), EType::Eyebrow, FSlateColor(Warn), false) ]
								+ SHorizontalBox::Slot().AutoWidth()[ ShadowText(Attr(CaptainStation), EType::Eyebrow, FSlateColor(Accent), false) ]
							]
							+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 6.f, 0.f, 2.f)[ ShadowText(Attr(CaptainText), EType::Ui, FSlateColor(Fg), true) ]
							+ SVerticalBox::Slot().AutoHeight()[ SNew(SBox).Visibility_Lambda([this]() { return CaptainHint.IsEmpty() ? EVisibility::Collapsed : EVisibility::HitTestInvisible; })[ ShadowText(Attr(CaptainHint), EType::Small, FSlateColor(Muted), true) ] ])
					]
				]
				// Toasts: the boat's status line (shown in every mode: Off keeps toasts).
				+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Right).Padding(0.f, 0.f, 0.f, 10.f)
				[
					SNew(SBox).Visibility_Lambda([this]() { return bToast ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
					[ MessageCard([this]() { return ToastColor; }, ShadowText(Attr(ToastText), EType::Ui, FSlateColor(Fg), true)) ]
				]
				// Rules points: the number large in its colour, then what it was for.
				+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Right).Padding(0.f, 0.f, 0.f, 10.f)
				[
					SNew(SBox).Visibility_Lambda([this]() { return bPoints && Mode < 2 ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
					[
						MessageCard([this]() { return PointsColor; }, SNew(SHorizontalBox)
							+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(0.f, 0.f, 14.f, 0.f)[ ShadowText(Attr(PointsValue), EType::CardTitleM, ColorAttr(PointsColor), false) ]
							+ SHorizontalBox::Slot().FillWidth(1.f).VAlign(VAlign_Center)[ ShadowText(Attr(PointsText), EType::Ui, FSlateColor(Fg), true) ])
					]
				]
				// Signals heard and vessels keeping clear: the last 8 seconds.
				+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Right).Padding(0.f, 0.f, 0.f, 10.f)
				[
					SNew(SBox).Visibility_Lambda([this]() { return bSignals && Mode < 2 ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
					[ MessageCard([]() { return WindTrue; }, ShadowText(Attr(SignalsText), EType::Ui, FSlateColor(Fg), true)) ]
				]
				// Sound captions show even with the HUD off (Mode 2): they stand in for what a player can't hear.
				+ SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Right)
				[
					SNew(SBox).Visibility_Lambda([this]() { return bCaptions ? EVisibility::HitTestInvisible : EVisibility::Collapsed; })
					[ MessageCard([]() { return Muted; }, ShadowText(Attr(CaptionsText), EType::Ui, FSlateColor(Fg), true)) ]
				]
			]
		]
		]
		]
		]
	];
	Refresh();
}

bool SSailHud::RightPanelsShown() const
{
	return ((bDrill || bRace) && Mode < 2) || (bNav && Mode == 0);
}

float SSailHud::MessageWidthFor(float Width, bool bRightPanels)
{
	// The stack's right edge, and room from there back to just right of the screen's centre (where the boat sits).
	const float Right = Width - SailUI::HudMargin - (bRightPanels ? RightColumnWidth + MessageGap : 0.f);
	const float Room = Right - (Width * 0.5f + 40.f);
	return FMath::Clamp(Room, MessageMinWidth, MessageMaxWidth);
}

ASailboatPawn* SSailHud::Pawn() const
{
	return Player.IsValid() ? Cast<ASailboatPawn>(Player->GetPawn()) : nullptr;
}

FLinearColor SSailHud::NightColor(const FLinearColor& C, float Amount, bool bTint)
{
	if (Amount <= 0.f) return C;
	// Red carries the colour's brightness (an aqua needle or a green word would otherwise go black), then green and blue
	// are cut: what is left is the deep red a chart table's night lamp gives.
	const float Lum = 0.2126f * C.R + 0.7152f * C.G + 0.0722f * C.B;
	FLinearColor N(FMath::Max(C.R, Lum), C.G, C.B, C.A);
	if (bTint) { N.G *= NightTintGreen; N.B *= NightTintBlue; }
	return FMath::Lerp(C, N, FMath::Clamp(Amount, 0.f, 1.f));
}

float SSailHud::NightHudAmount(float NightAmount, bool bEnabled)
{
	// The environment's night runs 0 at a sun 2 degrees down to 1 at 12; the red comes in through the middle of it
	// (about 5 to 9.5 degrees down: the end of civil twilight), in 1/16 steps so the cached HUD repaints a few times, not
	// every frame of the dusk.
	if (!bEnabled) return 0.f;
	return FMath::RoundToFloat(FMath::SmoothStep(0.3f, 0.75f, NightAmount) * 16.f) / 16.f;
}

FString SSailHud::MiniMapScaleBar(double SpanM, float WidthPx, float& OutBarPx)
{
	// The longest of these that fits in 40% of the map's width; under the shortest, the shortest.
	static const double Lengths[] = { 5.0, 2.0, 1.0, 0.5, 0.25, 0.1 };
	static const TCHAR* Names[] = { TEXT("5 nm"), TEXT("2 nm"), TEXT("1 nm"), TEXT("0.5 nm"), TEXT("0.25 nm"), TEXT("0.1 nm") };
	const double PxPerM = SpanM > 0.0 ? double(WidthPx) / SpanM : 0.0;
	int32 Pick = int32(UE_ARRAY_COUNT(Lengths)) - 1;
	if (PxPerM > 0.0) for (int32 I = 0; I < int32(UE_ARRAY_COUNT(Lengths)); ++I)
	{
		if (Lengths[I] * 1852.0 * PxPerM <= double(WidthPx) * 0.4) { Pick = I; break; }
	}
	OutBarPx = float(Lengths[Pick] * 1852.0 * PxPerM);
	return Names[Pick];
}

void SSailHud::Tick(const FGeometry& G, const double Now, const float Dt)
{
	SCompoundWidget::Tick(G, Now, Dt);
	SAILING_PERF_SCOPE(Hud);
	{
		// -SailingNightHud=<0..1> forces the palette for stills (0 holds the day colours at night).
		static uint32 ArgGen = MAX_uint32;
		static float ArgNight = -1.f;
		if (ArgGen != SailingArgs::Generation())
		{
			ArgGen = SailingArgs::Generation();
			ArgNight = -1.f;
			float V = 0.f;
			if (SailingArgs::LastValue(SailingArgs::Dev(), TEXT("SailingNightHud="), V)) ArgNight = FMath::Clamp(V, 0.f, 1.f);
		}
		float NightNow = 0.f;
		if (ArgNight >= 0.f) NightNow = ArgNight;
		else if (const UWorld* World = Player.IsValid() ? Player->GetWorld() : nullptr)
		{
			if (!Environment.IsValid()) for (TActorIterator<ASailingEnvironment> It(World); It; ++It) Environment = *It;
			if (Environment.IsValid()) NightNow = NightHudAmount(Environment->GetNightAmount(), USailingSettings::Get()->bNightHud);
		}
		SailHudImpl::NightHud = NightNow;
	}
	LayoutWidth = float(G.GetLocalSize().X) / SailHudImpl::HudScaleNow();
	// The right-hand column: shed whole lines, one fit level at a time, while the panels outgrow the room between the
	// minimap and the sail trim panel; take them back once the room holds the height measured before each level. A level
	// waits for the layout to show the last one (RightFitHold) and starts again from 0 when the panels shown change.
	if (RightPanels.IsValid() && RightPanelsRoom.IsValid())
	{
		const uint32 Key = (bDrill ? 1u : 0u) | (bRace ? 2u : 0u) | (bNav ? 4u : 0u) | (uint32(Mode) << 3);
		if (Key != RightFitKey)
		{
			RightFitKey = Key;
			if (RightFit != 0) { RightFit = 0; DrillSteps.Reset(); NextRefresh = 0.0; }
			RightFitHold = Now + 0.05;
		}
		const float Room = float(RightPanelsRoom->GetTickSpaceGeometry().GetLocalSize().Y);
		const float Wanted = float(RightPanels->GetDesiredSize().Y);
		if (Now >= RightFitHold && Room > 0.f)
		{
			int32 NewFit = RightFit;
			if (Wanted > Room + 1.f && RightFit < RightFitMax) { RightFitHeights[RightFit] = Wanted; NewFit = RightFit + 1; }
			else if (RightFit > 0 && Room >= RightFitHeights[RightFit - 1] + 8.f) NewFit = RightFit - 1;
			if (NewFit != RightFit)
			{
				RightFit = NewFit;
				DrillSteps.Reset();     // rebuild the drill list at the new level
				NextRefresh = 0.0;      // this tick, so the next layout already shows it
				RightFitHold = Now + 0.05;
			}
		}
	}
	// The left-hand column: drop the tip card's and the rules callout's explainers when they outgrow the room above the
	// instruments.
	if (LeftPanels.IsValid() && LeftPanelsRoom.IsValid())
	{
		const float Room = float(LeftPanelsRoom->GetTickSpaceGeometry().GetLocalSize().Y);
		const float Wanted = float(LeftPanels->GetDesiredSize().Y);
		if (!bCompactLeft && Room > 0.f && Wanted > Room + 1.f) { bCompactLeft = true; FullLeftHeight = Wanted; }
		else if (bCompactLeft && Room >= FullLeftHeight + 8.f) bCompactLeft = false;
	}
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
	const USailingSettings* U = USailingSettings::Get();
	WindText = FText::FromString(FString::Printf(TEXT("%.0f %s %s G%.0f"), U->SpeedIn(T.TrueWindSpeed), U->SpeedUnit(), *USailSessionSubsystem::CompassPoint(float(Wx.Wind.FromDegrees)),
		U->SpeedIn(T.TrueWindSpeed) * (1.0 + Wx.Wind.GustIntensity)));
	const USailSessionSubsystem* Session = USailSessionSubsystem::Get(P);
	// Without a session's own temperature, the weather's air (the mistral's cold 13 C).
	const float TempF = Session && Session->bHasActive ? Session->Active.Conditions.AirTempF : float(Wx.AirC * 9.0 / 5.0 + 32.0);
	SkyText = FText::FromString(FString::Printf(TEXT("%s · %.0f°F"), UTF8_TO_TCHAR(WeatherPresetName(GM->GetWeather().GetPreset())), TempF));
	bTidal = Lake.IsTidal();
	bCoast = Lake.IsCoast();
	if (bTidal)
	{
		const Vec3 O = P->GetBoatModel().OriginPosition();
		const Vec3 Cur = GM->GetCurrentAt(O.X, O.Y);
		const double Kn = FMath::Sqrt(Cur.X * Cur.X + Cur.Y * Cur.Y) / kKnot;
		FTideEvent Next;
		const bool bNext = GM->GetNextTide(Next);
		TideText = FText::FromString(FString::Printf(TEXT("%s %.1f kn"), bNext ? (Next.Type == FTideEvent::High ? TEXT("Flooding") : TEXT("Ebbing")) : TEXT("Tide"), Kn));
	}
	// Heading: magnetic by default (the world's variation), true if Settings > Gameplay says so.
	const bool bMagnetic = !U->bHeadingsTrue && Lake.VariationDeg != 0.0;   // the lake's bake has no variation: true there
	const double Hdg = FMath::Fmod(P->GetHeadingTrueDeg() - (bMagnetic ? Lake.VariationDeg : 0.0) + 720.0, 360.0);
	HeadingText = FText::FromString(FString::Printf(TEXT("%03.0f°%s"), Hdg, bMagnetic ? TEXT("M") : TEXT("T")));
	const double Twa = FMath::RadiansToDegrees(T.TrueWindAngle);
	const double Stw = T.SpeedThroughWater / kKnot;
	const USailingSettings* Units = USailingSettings::Get();
	const double Shown = Units->SpeedIn(T.SpeedThroughWater);
	SpeedText = FText::FromString(FString::Printf(TEXT("%.1f"), FMath::Abs(Stw) < 0.05 ? 0.0 : Shown));
	SpeedUnitText = FText::FromString(Units->SpeedUnit());
	SpeedSub = FText::FromString(FString::Printf(TEXT("VMG %.1f · target %.1f"), Units->SpeedIn(T.VMG), Units->SpeedIn(TargetKnots(int32(Cfg.Type), T.TrueWindSpeed / kKnot, Twa) * kKnot)));
	const double Awa = FMath::RadiansToDegrees(T.ApparentWindAngle);
	AwaText = FText::FromString(FString::Printf(TEXT("%.0f° %s"), FMath::Abs(Awa), Awa >= 0.0 ? TEXT("S") : TEXT("P")));
	AwsText = FText::FromString(FString::Printf(TEXT("APP WIND · %.1f %s"), Units->SpeedIn(T.ApparentWindSpeed), *FString(Units->SpeedUnit()).ToUpper()));
	// Depth below the surface (the keel's depth plus what is under it); the alarm is 2 ft under the keel.
	const double DepthM = T.DepthUnderKeel + Cfg.Draft, AlarmM = Cfg.Draft + 0.6096;
	const double DepthShown = Units->DepthIn(DepthM);
	DepthText = FText::FromString(DepthShown < 10.0 && Units->DepthUnits != 0 ? FString::Printf(TEXT("%.1f"), DepthShown) : FString::Printf(TEXT("%.0f"), FMath::Min(DepthShown, 999.0)));
	DepthUnitText = FText::FromString(Units->DepthUnit());
	DepthSub = FText::FromString(FString::Printf(TEXT("Keel %.1f · alarm %.1f"), Units->DepthIn(Cfg.Draft), Units->DepthIn(AlarmM)));
	bShallow = DepthM < AlarmM;
	PointText = FText::FromString(P->IsTiedUp() ? FString(TEXT("Tied up"))   // feedback #488: not "In irons" at the dock
		: FString::Printf(TEXT("%s · %s"), *SailingPointOfSail(Twa, T.bInIrons), Twa >= 0.0 ? TEXT("starboard") : TEXT("port")));
	// The tip card: the coach's most pressing tip, kept at least 6 s unless something worse comes up.
	const USailingSettings* S = USailingSettings::Get();
	const bool bTipsOn = S->bLearningMode && (!Session || !Session->bHasActive || Session->Active.bLearningTips);
	TArray<TPair<FString, int32>> Tips;
	SailingCollectTips(*P, P->GetWorld(), Tips);
	const TPair<FString, int32>* Best = nullptr;
	for (int32 I = 1; I < Tips.Num(); ++I) if (!Best || Tips[I].Value > Best->Value) Best = &Tips[I];
	const double Now = FPlatformTime::Seconds();
	// Graphics G7: a tip the learning coach raised on an event (learning-tips.json) wins while it is up.
	const FLearningTip* Learned = P->GetLearning().Current(P->GetSimTime());
	if (Learned && (!Best || Learned->Level >= Best->Value || P->GetLearning().CurrentText() == LastTip))
	{
		const FString Body = P->GetLearning().CurrentText();
		if (Body != LastTip)
		{
			LastTip = Body;
			TipShownAt = Now;
			TipTitle = FText::FromString(LearningTopicName(Learned->Topic));
			TipBody = FText::FromString(Body);
		}
	}
	else if (Best && (Best->Key != LastTip) && (Now - TipShownAt > TipHoldSeconds || Best->Value >= 2))
	{
		LastTip = Best->Key;
		TipShownAt = Now;
		const int32 Dot = Best->Key.Find(TEXT(":"));
		TipTitle = FText::FromString(Dot > 0 ? Best->Key.Left(Dot) : Tips[0].Key);
		TipBody = FText::FromString(Dot > 0 ? Best->Key.Mid(Dot + 1).TrimStart() : Best->Key);
	}
	if (P->IsTiedUp() && !Learned) LastTip.Reset();   // feedback #488: no sailing tip left on the card at the dock
	// The trim panel's headline: the same telemetry, moment and hold as the card (#712's third Mac stills: judged every
	// frame, it caught a two-strip stall between the card's 10 Hz looks and held it, beside a card saying all was well).
	TrimShown = HoldTrimVerdict(TrimHold, TrimVerdict(T, Cfg, P->GetEasyAssists(), P->IsTiedUp(), P->GetSecondsSinceStart() < SailingNoGoTipHoldSeconds), Now);
	// (While muted the coach's tips are consumed unseen: the card's last tip is cleared, so none from the scene's time shows
	// once it lifts.)
	const bool bMuted = TipsMutedByScene(GM->GetScene(), GM->IsSceneHandoverPending());
	if (bMuted) LastTip.Reset();
	bTip = bTipsOn && !LastTip.IsEmpty() && !bMuted;
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
		// The briefing's wording (keys follow rebinding) and, in learning mode, the coach's line under the current step.
		const FDrillBriefing* Brief = FLearningContent::Get().Briefing(D.GetDrill(), D.IsDinghyRun());
		const bool bBrief = Brief && Brief->Steps.Num() == D.GetSteps().Num();
		TArray<TTuple<FString, int32, FString>> Steps;
		for (int32 I = 0; I < D.GetSteps().Num(); ++I)
		{
			const int32 State = D.IsComplete() || I < D.GetStep() ? 2 : (I == D.GetStep() ? 1 : 0);
			Steps.Add({ bBrief ? Brief->StepText(I) : D.GetSteps()[I], State, bBrief && State == 1 && S->bLearningMode ? Brief->Steps[I].Coach : FString() });
		}
		// Short of room above the sail trim panel (RightFit): the footer keeps only the drill's status, then the coach's line
		// goes, then every step but the current one (with "Step k of n").
		if (Fit(1)) DrillFooter = FText::FromString(D.GetStatus());
		if (Fit(2)) for (TTuple<FString, int32, FString>& Row : Steps) Row.Get<2>().Reset();
		if (Fit(3) && Steps.Num() > 0)
		{
			const int32 Current = FMath::Clamp(D.IsComplete() ? Steps.Num() - 1 : D.GetStep(), 0, Steps.Num() - 1);
			Steps = { Steps[Current] };
			DrillFooter = FText::FromString(D.GetStatus().IsEmpty() ? FString::Printf(TEXT("Step %d of %d"), Current + 1, D.GetSteps().Num())
				: FString::Printf(TEXT("Step %d of %d · %s"), Current + 1, D.GetSteps().Num(), *D.GetStatus()));
		}
		if (Steps != DrillSteps)
		{
			DrillSteps = Steps;
			DrillList->ClearChildren();
			for (const TTuple<FString, int32, FString>& Row : Steps)
			{
				const TPair<FString, int32> St(Row.Get<0>(), Row.Get<1>());
				const FString& Coach = Row.Get<2>();
				DrillList->AddSlot().AutoHeight().Padding(0.f, 3.f)
				[
					SNew(SHorizontalBox)
					+ SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Top).Padding(0.f, 3.f, 10.f, 0.f)
					[ SNew(SBox).WidthOverride(12.f).HeightOverride(12.f)[ SNew(SBorder).BorderImage(Rounded(St.Value == 2 ? Starboard : (St.Value == 1 ? Accent : FLinearColor::Transparent), 2.f, St.Value == 0 ? Muted : FLinearColor::Transparent, 1.5f)) ] ]
					+ SHorizontalBox::Slot().FillWidth(1.f)
					[
						SNew(SVerticalBox)
						+ SVerticalBox::Slot().AutoHeight()[ SailUI::Text(St.Key, St.Value == 1 ? EType::Ui : EType::Small, St.Value == 2 ? Muted : Fg, true) ]
						+ SVerticalBox::Slot().AutoHeight().Padding(0.f, 3.f, 0.f, 2.f)[ Coach.IsEmpty() ? SNullWidget::NullWidget : SailUI::Text(Coach, EType::Small, Muted, true) ]
					]
				];
			}
		}
	}
	// Sound captions (Settings > Accessibility): what was heard and from where, in brackets as captions are.
	{
		const USoundCaptions* Captions = USoundCaptions::Get(P);
		const TArray<FString> Heard = Captions && U->bSoundCaptions ? Captions->Active() : TArray<FString>();
		bCaptions = Heard.Num() > 0;
		CaptionsText = bCaptions ? FText::FromString(TEXT("[") + FString::Join(Heard, TEXT("]\n[")) + TEXT("]")) : FText::GetEmpty();
	}
	RefreshScene(*P, *GM);
	RefreshTraffic(*P, *GM);
	// -SailingHudSample (docs/hud-layout/): a toast, a points card and a signal held up for layout stills at any size.
	static SailingArgs::FCachedFlag HudSampleArg(TEXT("SailingHudSample"));
	if (HudSampleArg.Get())
	{
		bToast = true;
		ToastText = FText::FromString(TEXT("Good tack: lost 0.9 kn, back up to speed in 6 s"));
		ToastColor = Starboard;
		bPoints = true;
		PointsValue = FText::FromString(TEXT("+20"));
		PointsText = FText::FromString(TEXT("Kept clear of the starboard tacker"));
		PointsColor = Starboard;
		bSignals = true;
		SignalsText = FText::FromString(TEXT("Five short blasts from the power boat ahead\nJ/22 Bluebird keeping clear astern"));
	}
	// Key hints: up to three, from the situation.
	TArray<FString> Hints;
	if (T.bCapsized && Cfg.RightingLever > 0.0) Hints.Add(KeyName(TEXT("Righting"), false) + TEXT("  Right the boat"));
	const FString SteerPort = KeyName(TEXT("Tiller"), true), SteerStbd = KeyName(TEXT("Tiller"), false);
	// Prologue step 2: away from the helm the crew steer; the hint is the station key instead.
	const Sailing::FStationControls& Stations = P->GetStations();
	if (!Stations.IsActive() || Stations.GetStation() == Sailing::ECrewStation::Helm) Hints.Add((SteerPort == SteerStbd ? SteerPort : SteerPort + TEXT(" / ") + SteerStbd) + TEXT("  Steer"));
	else Hints.Add(KeyName(TEXT("Station"), false) + TEXT("  Next station"));
	if (bCoast) Hints.Add(KeyName(TEXT("Chart"), false) + TEXT("  Chart"));
	// The keyboard's is Esc, the fixed key (ASailboatPawn::MapFixedKeys); the rebindable one works too.
	Hints.Add((SailUI::UsingGamepad() ? KeyName(TEXT("Menu"), false) : FString(TEXT("Esc"))) + TEXT("  Pause"));
	while (Hints.Num() > 3) Hints.RemoveAt(1);
	HintsText = FText::FromString(FString::Join(Hints, TEXT("     ")));
}

int32 SSailHud::TrimStripAt(float HeightFraction, int32 NumStrips)
{
	// The 3D ribbons' mapping (SailVisuals.cpp): the strip whose band holds that height.
	return FMath::Clamp(int32(HeightFraction * NumStrips), 0, FMath::Max(NumStrips - 1, 0));
}

ETelltaleState SSailHud::TrimYarnState(const FSailStripState* Strips, int32 NumStrips, int32 Band, ETrimYarn Yarn)
{
	auto Rule = [Yarn](const FSailStripState& St)
	{
		return Yarn == ETrimYarn::Leech ? LeechTelltaleState(St) : JibTelltaleState(St, Yarn == ETrimYarn::LuffWindward);
	};
	// Worse is further from streaming: a lift or a flutter, then a stall.
	auto Rank = [](ETelltaleState St) { return St == ETelltaleState::Stalled ? 2 : St == ETelltaleState::Streaming ? 0 : 1; };
	if (!Strips || NumStrips <= 0) return ETelltaleState::Streaming;
	ETelltaleState Worst = ETelltaleState::Streaming;
	bool bAny = false;
	for (int32 I = 0; I < NumStrips; ++I)
	{
		// A strip belongs to the third that holds its middle.
		if (FMath::Clamp(int32((I + 0.5f) * 3.f / NumStrips), 0, 2) != Band) continue;
		const ETelltaleState St = Rule(Strips[I]);
		if (!bAny || Rank(St) > Rank(Worst)) Worst = St;
		bAny = true;
	}
	return bAny ? Worst : Rule(Strips[TrimStripAt((Band + 0.5f) / 3.f, NumStrips)]);
}

SSailHud::FTrimVerdict SSailHud::TrimVerdict(const FBoatTelemetry& T, const FBoatConfig& Cfg, const FEasyAssists& Easy, bool bTiedUp, bool bHoldNoGo)
{
	// The coach's tips in one line (SailingCollectBoatTips, SailingHUD.cpp): the same no-go cue, the same counts over every
	// strip, the same thresholds and gate, so the panel's headline and the tip card agree (#712's first Mac stills said
	// "Sailing well" beside "Too close to the wind" and "Jib is stalled"). SailingSim.UI.TrimVerdict holds them together.
	// The most urgent first: the dock, irons, heel past the boat's limit, the no-go zone, then the sails.
	auto Make = [](const TCHAR* Head, const TCHAR* Say, bool bGood = false) { FTrimVerdict V; V.Head = Head; V.Say = Say; V.bGood = bGood; return V; };
	if (bTiedUp)
	{
		FTrimVerdict V = Make(TEXT("Tied up"), TEXT(""));
		V.bNeutral = true;
		return V;
	}
	if (T.bInIrons) return Make(TEXT("In irons"), TEXT("Bear away until the sails fill."));
	if (!Cfg.bMultihull && FMath::Abs(FMath::RadiansToDegrees(T.Heel)) > Cfg.TrimHeelLimitDeg) return Make(TEXT("Heeling too much"), TEXT("Ease the main or hike out."));
	const ENoGoCue Cue = NoGoCueFor(T, Easy);
	if (!bHoldNoGo && Cue == ENoGoCue::Inside) return Make(TEXT("Too close to the wind"), TEXT("Bear away to about 45 degrees."));
	if (!bHoldNoGo && Cue == ENoGoCue::Near) return Make(TEXT("Near the no-go zone"), TEXT("Bear away a little before she slows."));

	const double Twa = FMath::Abs(FMath::RadiansToDegrees(T.TrueWindAngle));
	if (Twa >= 35.0)
	{
		auto Count = [](const FSailStripState* Strips, int32 N, bool bLuff)
		{
			int32 K = 0;
			for (int32 I = 0; I < N; ++I)
			{
				const ESailFlow F = Strips[I].Flow;
				if (bLuff ? (F == ESailFlow::Luffing || F == ESailFlow::Backed) : F == ESailFlow::Stalled) ++K;
			}
			return K;
		};
		const bool bJib = T.NumJibStrips > 0;
		if (bJib && Count(T.JibStrips, T.NumJibStrips, true) >= 2)
			return Make(TEXT("Jib luffing"), Twa < 60.0 ? TEXT("Inside yarns lifting. Sheet in or bear away.") : TEXT("Inside yarns lifting. Sheet the jib in."));
		if (bJib && Count(T.JibStrips, T.NumJibStrips, false) >= 2) return Make(TEXT("Jib too tight"), TEXT("Outside yarns drooping. Ease the jib."));
		// With no jib (the Sunfish) the panel's luff window is the main's own luff.
		if (Count(T.MainStrips, T.NumMainStrips, true) >= 2)
			return bJib ? Make(TEXT("Main luffing"), TEXT("Leech ribbons flapping. Sheet the main in."))
				: Make(TEXT("Sail luffing"), TEXT("Inside yarns lifting. Sheet in."));
		if (Count(T.MainStrips, T.NumMainStrips, false) >= 2)
			return bJib ? Make(TEXT("Main too tight"), TEXT("Leech ribbons curling. Ease the main."))
				: Make(TEXT("Sail too tight"), TEXT("Yarns drooping and curling. Ease the sheet."));
	}
	// Well trimmed for the tips (one strip is not a call), but the line says what the panel's yarns show rather than
	// "streaming" beside one that curls (#712's second Mac stills: the bottom leech ribbon curled under "Yarns streaming").
	const bool bJib = T.NumJibStrips > 0;
	const FSailStripState* Luff = bJib ? T.JibStrips : T.MainStrips;
	const int32 NumLuff = bJib ? T.NumJibStrips : T.NumMainStrips;
	int32 Lifting = 0;
	bool bDroop = false, bCurl = false;
	for (int32 Band = 0; Band < 3; ++Band)
	{
		if (TrimYarnState(Luff, NumLuff, Band, ETrimYarn::LuffWindward) == ETelltaleState::Lifting) ++Lifting;
		if (TrimYarnState(Luff, NumLuff, Band, ETrimYarn::LuffLeeward) == ETelltaleState::Stalled) bDroop = true;
		if (T.NumMainStrips > 0 && TrimYarnState(T.MainStrips, T.NumMainStrips, Band, ETrimYarn::Leech) == ETelltaleState::Stalled) bCurl = true;
	}
	const TCHAR* Say = bCurl ? (bJib ? TEXT("A leech ribbon is curling. Ease the main a touch.") : TEXT("A leech ribbon is curling. Ease the sheet a touch."))
		: bDroop ? TEXT("An outside yarn is drooping. Ease the jib a touch.")
		: Lifting >= 2 ? TEXT("Inside yarns just lifting. Right on the edge.")
		: TEXT("Yarns streaming. Hold course.");
	return Make(TEXT("Sailing well"), Say, true);
}

SSailHud::FTrimVerdict SSailHud::HoldTrimVerdict(FTrimVerdictHold& Hold, const FTrimVerdict& Fresh, double Now)
{
	auto Warns = [](const FTrimVerdict& V) { return !V.bGood && !V.bNeutral; };
	FTrimVerdict& Shown = Hold.Shown;
	if (FCString::Strcmp(Fresh.Head, Shown.Head) == 0)
	{
		// The same call: its line follows after a short hold, so a yarn on the edge doesn't blink it.
		if (FCString::Strcmp(Fresh.Say, Shown.Say) != 0 && Now - Hold.SayAt >= TrimSayHoldSeconds)
		{
			Shown.Say = Fresh.Say;
			Hold.SayAt = Now;
		}
	}
	else if (Fresh.bNeutral || Shown.bNeutral || Warns(Fresh) || Now - Hold.ShownAt >= (Warns(Shown) ? TipHoldSeconds : 0.0))
	{
		Shown = Fresh;
		Hold.ShownAt = Hold.SayAt = Now;
	}
	return Shown;
}

bool SSailHud::TipsMutedByScene(const Sailing::FScriptedScene* Scene, bool bHandoverPending)
{
	// Until it is done and handed over: #634's QA, the tips came back the moment the scene was done, beside the instructor's
	// last line, while the cut to the lesson was still to come.
	return Scene && Scene->IsLoaded() && (!Scene->IsComplete() || bHandoverPending);
}

FVector2f SSailHud::MiniMapPoint(const FVector2D& BoatMap, const FVector2D& TargetMap, double SpanM, const FVector2f& Origin, const FVector2f& Size, bool& bClamped)
{
	// Map frame: X north, Y east; the minimap is north up, so east is +x on screen and north is -y.
	const double Span = FMath::Max(SpanM, 1.0);
	FVector2f D(float((TargetMap.Y - BoatMap.Y) / Span) * Size.X, float(-(TargetMap.X - BoatMap.X) / Span) * Size.Y);
	const FVector2f Half = Size * 0.5f - FVector2f(6.f, 6.f);
	const float K = FMath::Max(FMath::Abs(D.X) / FMath::Max(Half.X, 1.f), FMath::Abs(D.Y) / FMath::Max(Half.Y, 1.f));
	bClamped = K > 1.f;
	if (bClamped) D /= K;
	return Origin + Size * 0.5f + D;
}

FVector2f SSailHud::MiniMapClearOf(const FVector2f& Q, float Radius, TArrayView<const FBox2f> Keep, const FVector2f& Origin, const FVector2f& Size)
{
	// An edge dot inside a kept corner slides along its edge until it clears it: on the top or bottom edge sideways (to the
	// side of the box nearer the map's middle), on the left or right edge down or up the same way.
	const float Edge = 7.f;
	const bool bTopBottom = Q.Y <= Origin.Y + Edge || Q.Y >= Origin.Y + Size.Y - Edge;
	const float MidX = Origin.X + Size.X * 0.5f, MidY = Origin.Y + Size.Y * 0.5f;
	FVector2f Out = Q;
	for (const FBox2f& B : Keep)
	{
		if (Out.X + Radius <= B.Min.X || Out.X - Radius >= B.Max.X || Out.Y + Radius <= B.Min.Y || Out.Y - Radius >= B.Max.Y) continue;
		if (bTopBottom) Out.X = (B.GetCenter().X < MidX) ? B.Max.X + Radius : B.Min.X - Radius;
		else Out.Y = (B.GetCenter().Y < MidY) ? B.Max.Y + Radius : B.Min.Y - Radius;
	}
	return Out;
}

void SSailHud::RefreshScene(const ASailboatPawn& P, const ASailingGameMode& GM)
{
	// What the sim's scene says now (rule 8: the scene judges, the HUD only shows its caption and the answering keys).
	const Sailing::FScriptedScene* Scene = GM.GetScene();
	const FString Caption = Scene ? FString(UTF8_TO_TCHAR(Scene->GetCaption().c_str())) : FString();
	bCaptain = !Caption.IsEmpty();
	CaptainText = FText::FromString(Caption);
	FString Hint;
	const Sailing::FSceneStep* Step = Scene ? Scene->GetStep() : nullptr;
	// #402: the speaker by the call's id: the first job's instructor, the prologue's captain.
	const bool bInstructor = Step && Step->Call.Id.rfind("instructor.", 0) == 0;
	CaptainWho = FText::FromString(bInstructor ? TEXT("Instructor") : TEXT("Captain"));
	// Step 2: the station the player works, and the key that answers the call there (or the one that gets them there).
	const Sailing::FStationControls& Stations = P.GetStations();
	FString StationName = Stations.IsActive() ? FString(UTF8_TO_TCHAR(Sailing::CrewStationName(Stations.GetStation()))).Replace(TEXT("-"), TEXT(" ")) : FString();
	CaptainStation = FText::FromString(StationName.IsEmpty() ? FString() : TEXT("You: ") + StationName);
	if (bCaptain && Step && Scene->GetPhase() == Sailing::FScriptedScene::EPhase::Calling && Stations.IsActive() && !Step->Station.empty()
		&& Sailing::CrewStationFromName(Step->Station) != Stations.GetStation())
	{
		Hint = FString::Printf(TEXT("%s: go to the %s"), *SailingBindings::Label(TEXT("Station"), false, false), *FString(UTF8_TO_TCHAR(Step->Station.c_str())).Replace(TEXT("-"), TEXT(" ")));
	}
	else if (bCaptain && Step && Scene->GetPhase() == Sailing::FScriptedScene::EPhase::Calling && Scene->GetControlsDone() < int32(Step->Expect.Controls.size()))
	{
		using SailingBindings::Label;
		const bool bEase = Step->Expect.By > 0.0 || Step->Expect.AtLeast >= 0.0;
		switch (Sailing::StationControlFromName(Step->Expect.Controls[size_t(Scene->GetControlsDone())]))
		{
		case Sailing::EStationControl::Wheel: Hint = FString::Printf(TEXT("%s / %s: turn the wheel"), *Label(TEXT("Tiller"), true, false), *Label(TEXT("Tiller"), false, false)); break;
		case Sailing::EStationControl::JibSheet: Hint = FString::Printf(TEXT("%s: ease the jib sheet"), *Label(TEXT("JibSheet"), false, false)); break;
		case Sailing::EStationControl::Grinder: Hint = FString::Printf(TEXT("%s: grind (tap or hold)"), *Label(TEXT("Grind"), false, false)); break;
		case Sailing::EStationControl::MainSheet: Hint = FString::Printf(TEXT("%s: %s the main"), *Label(TEXT("MainSheet"), !bEase, false), bEase ? TEXT("ease") : TEXT("trim")); break;
		case Sailing::EStationControl::Traveller: Hint = FString::Printf(TEXT("%s / %s: traveller"), *Label(TEXT("Traveler"), true, false), *Label(TEXT("Traveler"), false, false)); break;
		case Sailing::EStationControl::TravellerDump: Hint = FString::Printf(TEXT("%s: dump the traveller"), *Label(TEXT("TravellerDump"), false, false)); break;
		case Sailing::EStationControl::Count:
		default: break;
		}
	}
	else if (bCaptain && Step && Scene->GetPhase() == Sailing::FScriptedScene::EPhase::Calling)
	{
		using SailingBindings::Label;
		const Sailing::FSceneExpectation& E = Step->Expect;
		const FName Sheet = E.Sheet == "main" ? FName(TEXT("MainSheet")) : FName(TEXT("JibSheet"));
		const TCHAR* SheetName = E.Sheet == "main" ? TEXT("main") : TEXT("jib");
		switch (E.Type)
		{
		case Sailing::ESceneExpect::Action: Hint = FString::Printf(TEXT("%s: %s"), *Label(TEXT("CrewAction"), false, false), UTF8_TO_TCHAR(E.Action.c_str())); break;
		case Sailing::ESceneExpect::Sheet:
		{
			const bool bEase = E.By > 0.0 || E.AtLeast >= 0.0;
			Hint = FString::Printf(TEXT("%s: %s the %s"), *Label(Sheet, !bEase, false), bEase ? TEXT("ease") : TEXT("trim"), SheetName);
			break;
		}
		case Sailing::ESceneExpect::Tack:
		case Sailing::ESceneExpect::Gybe:
		case Sailing::ESceneExpect::Hold:
			Hint = FString::Printf(TEXT("%s / %s: steer"), *Label(TEXT("Tiller"), true, false), *Label(TEXT("Tiller"), false, false));
			break;
		case Sailing::ESceneExpect::None:
		case Sailing::ESceneExpect::Station:
		case Sailing::ESceneExpect::Count:
		default: break;
		}
	}
	CaptainHint = FText::FromString(Hint);
}

void SSailHud::RefreshTraffic(const ASailboatPawn& P, const ASailingGameMode& GM)
{
	using namespace SailUI;
	const USailingSettings* S = USailingSettings::Get();
	const FLakeData& Lake = GM.GetLake();
	const FBoatModel& Model = P.GetBoatModel();
	// The coast's navigation: GPS (when on), the tide and its next turn, the current, the passage's next waypoint.
	bNav = Lake.IsCoast();
	if (bNav)
	{
		const Vec3 V = Model.GetState().Velocity;
		const double Sog = FMath::Sqrt(V.X * V.X + V.Y * V.Y);
		TArray<FString> Lines;
		if (P.IsGpsShown())
		{
			const double Cog = SailingNav::NormalizeDeg(FMath::RadiansToDegrees(FMath::Atan2(V.Y, V.X)));
			Lines.Add(FString::Printf(TEXT("GPS  %.1f kn over ground, %03.0f°T"), Sog / kKnot, Sog > 0.1 ? Cog : P.GetHeadingTrueDeg()));
		}
		else
		{
			Lines.Add(TEXT("GPS off: dead reckoning"));
		}
		if (Lake.IsTidal())
		{
			FString Tide = FString::Printf(TEXT("Tide  %+.1f ft"), GM.GetTideHeight() / 0.3048);
			FTideEvent Next;
			if (GM.GetNextTide(Next))
			{
				const int32 Minutes = int32(FMath::Fmod((Next.Time + GM.GetUtcOffsetHours() * 3600.0) / 60.0, 1440.0));
				Tide += FString::Printf(TEXT(" · %s %s"), Next.Type == FTideEvent::High ? TEXT("high water") : TEXT("low water"), *SailCatalog::ClockText(Minutes / 60.f));
			}
			Lines.Add(Tide);
			const Vec3 Cur = GM.GetCurrentAt(Model.OriginPosition().X, Model.OriginPosition().Y);
			const double Drift = FMath::Sqrt(Cur.X * Cur.X + Cur.Y * Cur.Y);
			Lines.Add(Drift < 0.03 ? FString(TEXT("Current  slack")) : FString::Printf(TEXT("Current  %.1f kn setting %03.0f°T"), Drift / kKnot,
				SailingNav::NormalizeDeg(FMath::RadiansToDegrees(FMath::Atan2(Cur.Y, Cur.X)))));
		}
		NavText = FText::FromString(FString::Join(Lines, TEXT("\n")));
		const TArray<TPair<FString, FVector2D>>& Plan = Lake.Passage;
		FString NextLine;
		if (P.GetPassageIndex() >= 0 && P.GetPassageIndex() < Plan.Num())
		{
			const TPair<FString, FVector2D>& Waypoint = Plan[P.GetPassageIndex()];
			const FVector2D Here = P.GetMapPosition();
			const double Dist = FVector2D::Distance(Here, Waypoint.Value);
			const double Brg = SailingNav::TrueToMagnetic(SailingNav::BearingDeg(Here, Waypoint.Value), Lake.VariationDeg);
			NextLine = FString::Printf(TEXT("Next: %s, %s at %03.0f°M"), *Waypoint.Key, *SailingNav::FormatDistance(Dist), Brg);
			if (Sog > 0.5) NextLine += FString::Printf(TEXT(", %.0f min"), Dist / Sog / 60.0);
		}
		NextText = FText::FromString(NextLine);
	}

	const ATrafficManager* TM = ATrafficManager::Find(P.GetWorld());
	bCoach = bSignals = bRace = bPoints = false;
	if (!TM) return;
	const double Now = TM->GetSim().GetTime();
	const FRulesCoach& Coach = TM->GetCoach();
	// Learning: what the rules say about the vessel that matters most right now.
	const FRulesCoach::FAdvice& A = Coach.GetAdvice();
	bCoach = S->bLearningMode && A.bActive;
	if (bCoach)
	{
		CoachRole = FText::FromString(FString::Printf(TEXT("%s (%s)"), UTF8_TO_TCHAR(A.Role.c_str()), UTF8_TO_TCHAR(A.Rule.c_str())));
		CoachRoleColor = A.bGiveWay ? Warn : (A.bStandOn ? Starboard : Muted);
		CoachWho = FText::FromString(UTF8_TO_TCHAR(A.Who.c_str()));
		CoachAction = FText::FromString(UTF8_TO_TCHAR(A.Action.c_str()));
		CoachReason = FText::FromString(UTF8_TO_TCHAR(A.Reason.c_str()));
		const bool bCpa = A.Tcpa > 0.0 && A.Tcpa < 900.0;
		CoachCpa = bCpa ? FText::FromString(FString::Printf(TEXT("Closest approach %.0f m in %.0f s"), A.Cpa, A.Tcpa)) : FText::GetEmpty();
		CoachCpaColor = bCpa && A.Cpa < 30.0 ? Port : Muted;
	}
	// Signals heard, vessels keeping clear and the latest rules judgment: the last 8 seconds.
	TArray<FString> Heard;
	const std::vector<FRulesCoach::FScore>& Scores = Coach.GetScores();
	bPoints = !Scores.empty() && Now - Scores.back().Time < 8.0;
	if (bPoints)
	{
		PointsValue = FText::FromString(FString::Printf(TEXT("%+d"), Scores.back().Points));
		PointsText = FText::FromString(UTF8_TO_TCHAR(Scores.back().Text.c_str()));
		PointsColor = Scores.back().Points < 0 ? Port : Starboard;
	}
	const TArray<TPair<double, FString>>& Messages = TM->GetMessages();
	for (int32 I = Messages.Num() - 1; I >= 0 && Heard.Num() < 3; --I)
	{
		if (Now - Messages[I].Key > 8.0) break;
		Heard.Add(Messages[I].Value);
	}
	bSignals = Heard.Num() > 0;
	SignalsText = FText::FromString(FString::Join(Heard, TEXT("\n")));
	ScoreText = FText::FromString(!S->bLearningMode || !Scores.empty() ? FString::Printf(TEXT("Rules score %+d"), Coach.GetScore()) : FString());
	ScoreColor = Coach.GetScore() < 0 ? Port : Starboard;

	// The race.
	const FRaceRunner* R = TM->GetRace();
	bRace = R != nullptr;
	if (!R) return;
	const FRaceEntry* Me = R->FindEntry(FTrafficSim::PlayerId);
	const double ToStart = R->StartTime() - Now;
	const int32 Sec = FMath::Max(0, int32(FMath::Abs(ToStart)));
	RaceHeadColor = Fg;
	FString Head;
	switch (R->Phase(Now))
	{
	case FRaceRunner::EPhase::Warning: Head = FString::Printf(TEXT("Start in %d:%02d · class flag up"), Sec / 60, Sec % 60); break;
	case FRaceRunner::EPhase::Preparatory: Head = FString::Printf(TEXT("Start in %d:%02d · P flag up"), Sec / 60, Sec % 60); RaceHeadColor = Warn; break;
	case FRaceRunner::EPhase::OneMinute: Head = FString::Printf(TEXT("Start in 0:%02d · P flag down"), Sec); RaceHeadColor = Port; break;
	case FRaceRunner::EPhase::Racing: Head = FString::Printf(TEXT("Racing %d:%02d · %d of %d"), Sec / 60, Sec % 60, TM->GetRacePosition(), int32(R->Entries.size())); RaceHeadColor = Starboard; break;
	default: Head = TEXT("Race over"); break;
	}
	RaceHead = FText::FromString(Head);
	RaceTask = FText::GetEmpty();
	RaceLine = FText::GetEmpty();
	if (Me)
	{
		RaceTask = FText::FromString(UTF8_TO_TCHAR(R->NextTask(*Me).c_str()));
		RaceTaskColor = Me->bOcs ? Port : Fg;
		const FVector2D Pos = P.GetMapPosition();
		if (!Me->bStarted || Me->bOcs)
		{
			const double Side = R->Course.CourseSide(Pos.X, Pos.Y);
			RaceLine = FText::FromString(FString::Printf(TEXT("Line: %.0f m %s"), FMath::Abs(Side), Side > 0.0 ? TEXT("over, on the course side") : TEXT("below")));
			RaceLineColor = Side > 0.0 ? Port : Muted;
		}
		else if (Me->NextMark < int32(R->Course.Marks.size()))
		{
			const FRaceMark& Mk = R->Course.Marks[Me->NextMark];
			RaceLine = FText::FromString(FString::Printf(TEXT("%s: %.0f m at %03.0f°"), UTF8_TO_TCHAR(Mk.Name.c_str()), FVector2D::Distance(Pos, FVector2D(Mk.X, Mk.Y)),
				SailingNav::BearingDeg(Pos, FVector2D(Mk.X, Mk.Y))));
			RaceLineColor = Muted;
		}
	}
	FString Results;
	if (R->IsOver())
	{
		TArray<const FRaceEntry*> Sorted;
		for (const FRaceEntry& E : R->Entries) Sorted.Add(&E);
		Sorted.Sort([](const FRaceEntry& A2, const FRaceEntry& B2) { return A2.Points < B2.Points; });
		for (const FRaceEntry* E : Sorted)
		{
			const int32 Secs = int32(E->FinishTime - R->StartTime());
			Results += E->bFinished
				? FString::Printf(TEXT("%d. %s  %d:%02d  %d pt%s\n"), E->Place, UTF8_TO_TCHAR(E->Name.c_str()), Secs / 60, Secs % 60, E->Points, E->VesselId == FTrafficSim::PlayerId ? TEXT("  (you)") : TEXT(""))
				: FString::Printf(TEXT("–  %s  %s  %d pt\n"), UTF8_TO_TCHAR(E->Name.c_str()), UTF8_TO_TCHAR(E->Status.c_str()), E->Points);
		}
	}
	RaceResults = FText::FromString(Results.TrimEnd());
}
