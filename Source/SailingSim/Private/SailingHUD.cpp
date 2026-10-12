#include "SailingHUD.h"
#include "SailboatPawn.h"
#include "SailingSettings.h"
#include "SailingGameMode.h"
#include "Weather.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"

using namespace Sailing;

namespace
{
	const FLinearColor Panel(0.f, 0.f, 0.f, 0.45f);
	const FLinearColor Dim(0.75f, 0.8f, 0.85f);
	const FLinearColor Good(0.4f, 1.f, 0.5f);
	const FLinearColor Warn(1.f, 0.8f, 0.2f);
	const FLinearColor Bad(1.f, 0.35f, 0.3f);

	FString PointOfSail(double TwaDeg, bool bInIrons)
	{
		const double A = FMath::Abs(TwaDeg);
		if (bInIrons) return TEXT("In irons");
		if (A < 35.0) return TEXT("No-go zone (head to wind)");
		if (A < 50.0) return TEXT("Close-hauled");
		if (A < 80.0) return TEXT("Close reach");
		if (A < 100.0) return TEXT("Beam reach");
		if (A < 160.0) return TEXT("Broad reach");
		return TEXT("Run");
	}
}

void ASailingHUD::Text(const FString& Str, float X, float Y, const FLinearColor& Color, float Scale, bool bBig)
{
	UFont* Font = bBig ? GEngine->GetLargeFont() : GEngine->GetMediumFont();
	DrawText(Str, Color, X * UIScale, Y * UIScale, Font, Scale * UIScale);
}

void ASailingHUD::Bar(const FString& Label, float Value, float Lo, float Hi, float X, float Y, float Width, const FLinearColor& Color)
{
	const float T = FMath::Clamp((Value - Lo) / (Hi - Lo), 0.f, 1.f);
	Text(Label, X, Y - 2.f, Dim, 0.9f);
	const float BX = X + 110.f;
	DrawRect(FLinearColor(1, 1, 1, 0.15f), BX * UIScale, (Y + 3.f) * UIScale, Width * UIScale, 10.f * UIScale);
	if (Lo < 0.f)
	{
		const float Zero = (0.f - Lo) / (Hi - Lo);
		const float A = FMath::Min(Zero, T), B = FMath::Max(Zero, T);
		DrawRect(Color, (BX + A * Width) * UIScale, (Y + 3.f) * UIScale, FMath::Max(2.f, (B - A) * Width) * UIScale, 10.f * UIScale);
	}
	else
	{
		DrawRect(Color, BX * UIScale, (Y + 3.f) * UIScale, T * Width * UIScale, 10.f * UIScale);
	}
}

void ASailingHUD::DrawHUD()
{
	Super::DrawHUD();
	const ASailboatPawn* Boat = PlayerOwner ? Cast<ASailboatPawn>(PlayerOwner->GetPawn()) : nullptr;
	if (!Boat || !Canvas)
	{
		return;
	}
	UIScale = FMath::Clamp(Canvas->ClipY / 1080.f, 0.7f, 2.f);

	const USailingSettings* Settings = USailingSettings::Get();
	if (Boat->IsMenuOpen())
	{
		DrawMenu(*Boat);
		return;
	}
	if (Boat->IsControlsCardOpen())
	{
		DrawControlsCard(*Boat);
		return;
	}
	if (!Settings->bShowHud)
	{
		Text(TEXT("H: show instruments   ?: controls   Tab: settings"), 20.f, 20.f, Dim, 0.8f);
		return;
	}
	DrawInstruments(*Boat);
	DrawControls(*Boat);
	DrawWeather(*Boat);
	DrawDrillAndStatus(*Boat);
	if (Settings->bLearningMode)
	{
		DrawWindDiagram(*Boat, FVector2D(Canvas->ClipX / UIScale - 140.f, 160.f), 100.f);
		DrawTips(*Boat);
	}
}

void ASailingHUD::DrawInstruments(const ASailboatPawn& Boat)
{
	const FBoatTelemetry& T = Boat.GetBoatModel().GetTelemetry();
	DrawRect(Panel, 10.f * UIScale, 10.f * UIScale, 330.f * UIScale, 278.f * UIScale);

	double Heading = FMath::RadiansToDegrees(T.Heading);
	if (Heading < 0.0) Heading += 360.0;
	const double Twd = FMath::Fmod(Heading + FMath::RadiansToDegrees(T.TrueWindAngle) + 360.0, 360.0);
	const double Awa = FMath::RadiansToDegrees(T.ApparentWindAngle);
	const double Heel = FMath::RadiansToDegrees(T.Heel);
	const double HeelLeeward = Heel * Boat.GetBoatModel().GetState().WindwardSide;

	float Y = 18.f;
	Text(FString::Printf(TEXT("%.1f kn"), T.BoatSpeed / kKnot), 22.f, Y, FLinearColor::White, 1.6f, true);
	Text(TEXT("boat speed"), 200.f, Y + 12.f, Dim, 0.8f);
	Y += 46.f;
	Text(FString::Printf(TEXT("Heading   %03.0f"), Heading), 22.f, Y);
	Y += 24.f;
	Text(FString::Printf(TEXT("App. wind %3.0f %s  %.1f kn"), FMath::Abs(Awa), Awa >= 0.0 ? TEXT("stbd") : TEXT("port"), T.ApparentWindSpeed / kKnot), 22.f, Y);
	Y += 24.f;
	Text(FString::Printf(TEXT("True wind %03.0f  %.1f kn"), Twd, T.TrueWindSpeed / kKnot), 22.f, Y);
	Y += 24.f;
	Text(FString::Printf(TEXT("TWA       %3.0f %s"), FMath::Abs(FMath::RadiansToDegrees(T.TrueWindAngle)), T.TrueWindAngle >= 0.0 ? TEXT("(starboard tack)") : TEXT("(port tack)")), 22.f, Y);
	Y += 24.f;
	Text(FString::Printf(TEXT("Heel      %3.0f%s"), FMath::Abs(Heel), HeelLeeward < -1.0 ? TEXT("  to windward") : TEXT("")), 22.f, Y,
		FMath::Abs(Heel) > 25.0 ? Bad : (FMath::Abs(Heel) > 20.0 ? Warn : FLinearColor::White));
	Y += 24.f;
	Text(FString::Printf(TEXT("VMG       %.1f kn"), T.VMG / kKnot), 22.f, Y);
	Y += 24.f;
	Text(FString::Printf(TEXT("Leeway    %.1f"), FMath::Abs(FMath::RadiansToDegrees(T.Leeway))), 22.f, Y, Dim);
	Y += 26.f;
	// The boat and what she is carrying.
	const FBoatConfig& Cfg = Boat.GetBoatModel().GetConfig();
	const FBoatControls& C = Boat.GetControls();
	FString Rig = FString(Cfg.Name);
	if (Boat.GetBoatModel().GetState().Reef > 0) Rig += FString::Printf(TEXT(" | reef %d"), Boat.GetBoatModel().GetState().Reef);
	if (T.NumSpinStrips > 0) Rig += Cfg.bAsymmetricSpinnaker ? TEXT(" | gennaker") : TEXT(" | spinnaker");
	if (Cfg.HasBoard() && C.Board < 0.5) Rig += TEXT(" | board up");
	if (!Cfg.Engines.empty() && FMath::Abs(C.Throttle) > 0.02) Rig += FString::Printf(TEXT(" | engine %.0f%% %s"), FMath::Abs(C.Throttle) * 100.0, C.Throttle > 0.0 ? TEXT("ahead") : TEXT("astern"));
	Text(Rig, 22.f, Y, Good, 0.85f);
}

void ASailingHUD::DrawControls(const ASailboatPawn& Boat)
{
	const FBoatControls& C = Boat.GetControls();
	const FBoatTelemetry& T = Boat.GetBoatModel().GetTelemetry();
	const USailingSettings* Settings = USailingSettings::Get();
	const bool bSimple = Settings->UseSimpleControls();
	const float Height = bSimple ? 190.f : 290.f;
	const float X = 10.f, Top = Canvas->ClipY / UIScale - Height - 10.f;
	DrawRect(Panel, X * UIScale, Top * UIScale, 340.f * UIScale, Height * UIScale);

	float Y = Top + 10.f;
	const bool bAssist = Boat.IsTrimAssistActive();
	Text(FString::Printf(TEXT("%s | %s | %s%s"), Settings->bLearningMode ? TEXT("Learning") : TEXT("Game"),
		Settings->Difficulty == ESailingDifficulty::Easy ? TEXT("Easy") : TEXT("Realistic"), bSimple ? TEXT("Simple") : TEXT("Full"),
		bAssist ? TEXT(" | crew trimming") : TEXT("")), X + 12.f, Y, Good, 0.9f);
	Y += 26.f;
	Bar(TEXT("Tiller"), -C.Tiller, -1.f, 1.f, X + 12.f, Y, 190.f, FLinearColor(0.9f, 0.7f, 0.3f)); Y += 20.f;
	// Weather helm: how hard the tiller pulls (N), positive = boat wants to round up.
	Bar(FString::Printf(TEXT("Helm %3.0f N"), T.HelmForce), T.HelmForce, -60.f, 60.f, X + 12.f, Y, 190.f, T.HelmForce > 40.0 ? Warn : FLinearColor(0.6f, 0.8f, 1.f)); Y += 24.f;
	Bar(TEXT("Mainsheet"), 1.f - C.MainSheet, 0.f, 1.f, X + 12.f, Y, 190.f, FLinearColor(0.4f, 0.8f, 1.f)); Y += 20.f;
	const FBoatConfig& Cfg = Boat.GetBoatModel().GetConfig();
	if (C.bSpinnaker && Cfg.HasSpinnaker()) { Bar(TEXT("Spin sheet"), 1.f - C.SpinSheet, 0.f, 1.f, X + 12.f, Y, 190.f, FLinearColor(1.f, 0.45f, 0.4f)); Y += 20.f; }
	else if (Cfg.HasJib()) { Bar(TEXT("Jib sheet"), 1.f - C.JibSheet, 0.f, 1.f, X + 12.f, Y, 190.f, FLinearColor(0.4f, 0.8f, 1.f)); Y += 20.f; }
	else { Text(TEXT("(una rig: one sail)"), X + 12.f, Y - 2.f, Dim, 0.8f); Y += 20.f; }
	Bar(TEXT("Crew"), C.Hike, -1.f, 1.f, X + 12.f, Y, 190.f, FLinearColor(1.f, 0.8f, 0.2f)); Y += 20.f;
	if (!Cfg.Engines.empty() && FMath::Abs(C.Throttle) > 0.0)
	{
		Bar(TEXT("Throttle"), C.Throttle, -1.f, 1.f, X + 12.f, Y - 2.f, 190.f, FLinearColor(0.8f, 0.8f, 0.8f));
	}
	if (!bSimple)
	{
		Bar(TEXT("Traveler"), C.Traveler, -1.f, 1.f, X + 12.f, Y, 190.f, FLinearColor(0.7f, 0.7f, 1.f)); Y += 20.f;
		Bar(TEXT("Vang"), C.Vang, 0.f, 1.f, X + 12.f, Y, 190.f, Dim); Y += 20.f;
		Bar(TEXT("Cunningham"), C.Cunningham, 0.f, 1.f, X + 12.f, Y, 190.f, Dim); Y += 20.f;
		Bar(TEXT("Outhaul"), C.Outhaul, 0.f, 1.f, X + 12.f, Y, 190.f, Dim); Y += 20.f;
		Bar(TEXT("Backstay"), C.Backstay, 0.f, 1.f, X + 12.f, Y, 190.f, Dim); Y += 22.f;
	}
	else
	{
		Text(TEXT("Crew handles traveler and sail shape"), X + 12.f, Y, Dim, 0.8f); Y += 22.f;
	}
	Text(FString::Printf(TEXT("Wing-on-wing %s (G)   ? controls   Tab settings"), C.bWingOnWing ? TEXT("on") : TEXT("off")), X + 12.f, Y, Dim, 0.8f);
}

void ASailingHUD::DrawWeather(const ASailboatPawn& Boat)
{
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM) return;
	const FWeatherState& W = GM->GetWeatherState();
	const FBoatTelemetry& T = Boat.GetBoatModel().GetTelemetry();
	const float X = Canvas->ClipX / UIScale - 300.f, Y = Canvas->ClipY / UIScale - 112.f;
	DrawRect(Panel, X * UIScale, Y * UIScale, 290.f * UIScale, 100.f * UIScale);
	const int32 Hour = int32(W.HourOfDay), Minute = int32(FMath::Fmod(W.HourOfDay, 1.0) * 60.0);
	Text(FString::Printf(TEXT("%hs  %02d:%02d"), WeatherPresetName(GM->GetWeather().GetPreset()), Hour, Minute), X + 10.f, Y + 8.f, FLinearColor::White, 0.9f);
	Text(FString::Printf(TEXT("Wind %.0f kn  waves %.2f m"), T.TrueWindSpeed / kKnot, GM->GetWaves().SignificantHeight()), X + 10.f, Y + 32.f, Dim, 0.85f);
	Text(FString::Printf(TEXT("Visibility %.0f km%s"), W.VisibilityKm, W.Rain > 0.05 ? TEXT("  rain") : TEXT("")), X + 10.f, Y + 54.f, Dim, 0.85f);
	if (W.Storm != EStormPhase::None)
	{
		Text(FString(StormPhaseName(W.Storm)), X + 10.f, Y + 76.f, W.Storm == EStormPhase::GustFront || W.Storm == EStormPhase::Rain ? Bad : Warn, 0.9f);
	}
}

void ASailingHUD::DrawDrillAndStatus(const ASailboatPawn& Boat)
{
	const FBoatTelemetry& T = Boat.GetBoatModel().GetTelemetry();
	const float CX = Canvas->ClipX / UIScale * 0.5f;
	float Y = Canvas->ClipY / UIScale * 0.62f;
	if (T.bAground)
	{
		Text(TEXT("AGROUND"), CX - 70.f, Y, Bad, 1.6f, true);
		Text(TEXT("Ease the sheets, heel her (crew to leeward) and back off the way you came."), CX - 300.f, Y + 40.f, Bad, 0.85f);
		Y += 80.f;
	}
	else if (T.DepthUnderKeel < 1.0)
	{
		Text(FString::Printf(TEXT("Shoal water: %.1f m under the keel"), T.DepthUnderKeel), CX - 150.f, Y, Warn, 0.95f);
		Y += 30.f;
	}
	const FBoatConfig& Cfg = Boat.GetBoatModel().GetConfig();
	if (T.bCapsized)
	{
		Text(TEXT("CAPSIZED"), CX - 80.f, Y, Bad, 1.6f, true);
		Text(Cfg.RightingLever > 0.0 ? TEXT("Let the sheets go, point the bow toward the wind and press X to right her.")
			: TEXT("She will not come back up on her own. Press R to start again."), CX - 330.f, Y + 40.f, Bad, 0.85f);
		Y += 80.f;
	}
	else if (T.bFlyingHull)
	{
		Text(TEXT("Flying a hull"), CX - 60.f, Y, Good, 0.95f);
		Y += 30.f;
	}
	else if (T.bPlaning)
	{
		Text(TEXT("Planing"), CX - 40.f, Y, Good, 0.95f);
		Y += 30.f;
	}
	if (T.bCollision && T.BoatSpeed > 0.25 * kKnot) // lying quietly against the fenders is not news
	{
		Text(TEXT("Contact!"), CX - 50.f, Y, Bad, 1.1f, true);
		Y += 34.f;
	}
	const FString Msg = Boat.GetStatusMessage();
	if (!Msg.IsEmpty())
	{
		Text(Msg, CX - 220.f, Y, FLinearColor::White, 0.95f);
	}

	const FDrillRunner& D = Boat.GetDrill();
	if (D.GetDrill() == ESailingDrill::None) return;
	const TArray<FString>& Steps = D.GetSteps();
	const float X = 360.f, Top = 300.f, W = 520.f, H = 70.f + Steps.Num() * 24.f;
	DrawRect(Panel, X * UIScale, Top * UIScale, W * UIScale, H * UIScale);
	Text(FString::Printf(TEXT("Drill: %s%s"), DrillName(D.GetDrill()), D.IsComplete() ? TEXT("  (complete)") : TEXT("")), X + 12.f, Top + 8.f, D.IsComplete() ? Good : FLinearColor::White, 1.f);
	for (int32 I = 0; I < Steps.Num(); ++I)
	{
		const bool bCurrent = !D.IsComplete() && I == D.GetStep();
		const bool bDone = D.IsComplete() || I < D.GetStep();
		Text(FString::Printf(TEXT("%s %d. %s"), bDone ? TEXT("+") : (bCurrent ? TEXT(">") : TEXT(" ")), I + 1, *Steps[I]), X + 12.f, Top + 36.f + I * 24.f, bCurrent ? Warn : (bDone ? Good : Dim), 0.82f);
	}
	Text(D.GetStatus(), X + 12.f, Top + H - 26.f, FLinearColor::White, 0.82f);
}

void ASailingHUD::DrawMenu(const ASailboatPawn& Boat)
{
	const TArray<TPair<FString, FString>> Rows = Boat.GetMenuRows();
	const float W = 680.f, H = 120.f + Rows.Num() * 32.f;
	const float X = Canvas->ClipX / UIScale * 0.5f - W * 0.5f, Y = Canvas->ClipY / UIScale * 0.5f - H * 0.5f;
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.7f), X * UIScale, Y * UIScale, W * UIScale, H * UIScale);
	Text(TEXT("Settings"), X + 20.f, Y + 14.f, FLinearColor::White, 1.1f, true);
	for (int32 I = 0; I < Rows.Num(); ++I)
	{
		const bool bSel = I == Boat.GetMenuIndex();
		const float RY = Y + 60.f + I * 32.f;
		if (bSel) DrawRect(FLinearColor(0.3f, 0.5f, 0.8f, 0.5f), (X + 10.f) * UIScale, (RY - 4.f) * UIScale, (W - 20.f) * UIScale, 30.f * UIScale);
		Text(Rows[I].Key, X + 24.f, RY, bSel ? FLinearColor::White : Dim);
		Text(FString::Printf(TEXT("<  %s  >"), *Rows[I].Value), X + 260.f, RY, bSel ? Good : FLinearColor::White);
	}
	Text(TEXT("Up/Down choose, Left/Right change, Tab (Menu) closes"), X + 20.f, Y + H - 54.f, Dim, 0.8f);
	// Required attribution for the map data (OpenStreetMap is ODbL); see CREDITS.md.
	Text(TEXT("Map data (c) OpenStreetMap contributors, ODbL. Terrain: USGS 3DEP."), X + 20.f, Y + H - 30.f, Dim, 0.7f);
	Text(TEXT("Lake depths and levels: Texas Water Development Board."), X + 20.f, Y + H - 12.f, Dim, 0.7f);
}

void ASailingHUD::DrawControlsCard(const ASailboatPawn& Boat)
{
	const bool bSimple = USailingSettings::Get()->UseSimpleControls();
	TArray<TPair<FString, FString>> Lines = {
		{ TEXT("Steer (tiller)"), TEXT("A / D        Left stick") },
		{ TEXT("Mainsheet trim / ease"), TEXT("W / S        Right / left trigger") },
		{ TEXT("Jib sheet trim / ease"), TEXT("E / Q        Right / left bumper") },
		{ TEXT("Crew hike out / in"), TEXT("F / V        D-pad up / down") },
		{ TEXT("Wing-on-wing"), TEXT("G            X") },
		{ TEXT("Back the jib (heave to, irons)"), TEXT("B            Left stick press") },
		{ TEXT("Dock lines on / off"), TEXT("T            Right stick press") },
		{ TEXT("Spinnaker up / down (Q/E trims it)"), TEXT("N") },
		{ TEXT("Take a reef / shake out"), TEXT("M") },
		{ TEXT("Board or swing keel up / down"), TEXT("J") },
		{ TEXT("Right a capsized boat"), TEXT("X") },
		{ TEXT("Engine ahead / astern, neutral"), TEXT("= / -  (PgUp/PgDn), 0") },
		{ TEXT("Twin engines: pivot"), TEXT("[ / ]") },
	};
	if (!bSimple)
	{
		Lines.Add({ TEXT("Traveler windward / leeward"), TEXT("Z / C        D-pad left / right") });
		Lines.Add({ TEXT("Vang, cunningham, outhaul"), TEXT("1-2, 3-4, 5-6") });
		Lines.Add({ TEXT("Backstay ease / on"), TEXT("7 / 8        A / B") });
	}
	Lines.Append({
		{ TEXT("Learning mode"), TEXT("L            Y") },
		{ TEXT("Difficulty"), TEXT("K") },
		{ TEXT("Settings (weather, time, quality)"), TEXT("Tab          Menu") },
		{ TEXT("Instruments"), TEXT("H") },
		{ TEXT("Reset boat"), TEXT("R") },
		{ TEXT("Camera"), TEXT("Mouse, wheel  Right stick") },
		{ TEXT("Close this card"), TEXT("?            View") } });
	const float W = 700.f, H = 70.f + Lines.Num() * 28.f;
	const float X = Canvas->ClipX / UIScale * 0.5f - W * 0.5f, Y = Canvas->ClipY / UIScale * 0.5f - H * 0.5f;
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.7f), X * UIScale, Y * UIScale, W * UIScale, H * UIScale);
	Text(bSimple ? TEXT("Controls (Simple layout)") : TEXT("Controls (Full layout)"), X + 20.f, Y + 14.f, FLinearColor::White, 1.1f, true);
	for (int32 I = 0; I < Lines.Num(); ++I)
	{
		Text(Lines[I].Key, X + 24.f, Y + 60.f + I * 28.f, Dim);
		Text(Lines[I].Value, X + 360.f, Y + 60.f + I * 28.f, FLinearColor::White);
	}
}

void ASailingHUD::DrawWindDiagram(const ASailboatPawn& Boat, const FVector2D& Center, float Radius)
{
	// Boat-up diagram: true wind (blue) and apparent wind (yellow) arrows point where the wind comes from.
	const FBoatTelemetry& T = Boat.GetBoatModel().GetTelemetry();
	const FVector2D C = Center * UIScale;
	const float R = Radius * UIScale;
	DrawRect(Panel, C.X - R - 20.f * UIScale, C.Y - R - 30.f * UIScale, 2.f * R + 40.f * UIScale, 2.f * R + 60.f * UIScale);
	for (int32 I = 0; I < 36; ++I)
	{
		const float A0 = I * 10.f * PI / 180.f, A1 = (I + 1) * 10.f * PI / 180.f;
		DrawLine(C.X + R * FMath::Sin(A0), C.Y - R * FMath::Cos(A0), C.X + R * FMath::Sin(A1), C.Y - R * FMath::Cos(A1), FLinearColor(1, 1, 1, 0.4f), 1.f);
	}
	// No-go zone, about 40 degrees either side of the true wind.
	const float Twa = float(T.TrueWindAngle);
	for (const float Edge : { Twa - 0.7f, Twa + 0.7f })
	{
		DrawLine(C.X, C.Y, C.X + R * FMath::Sin(Edge), C.Y - R * FMath::Cos(Edge), FLinearColor(1.f, 0.3f, 0.3f, 0.5f), 1.f);
	}
	// Boat silhouette pointing up.
	DrawLine(C.X, C.Y - 28.f * UIScale, C.X - 9.f * UIScale, C.Y + 22.f * UIScale, FLinearColor::White, 2.f);
	DrawLine(C.X, C.Y - 28.f * UIScale, C.X + 9.f * UIScale, C.Y + 22.f * UIScale, FLinearColor::White, 2.f);
	DrawLine(C.X - 9.f * UIScale, C.Y + 22.f * UIScale, C.X + 9.f * UIScale, C.Y + 22.f * UIScale, FLinearColor::White, 2.f);

	auto Arrow = [&](float Angle, float Len, const FLinearColor& Color)
	{
		const FVector2D Tip(C.X + R * FMath::Sin(Angle), C.Y - R * FMath::Cos(Angle));
		const FVector2D Tail(C.X + (R - Len) * FMath::Sin(Angle), C.Y - (R - Len) * FMath::Cos(Angle));
		DrawLine(Tip.X, Tip.Y, Tail.X, Tail.Y, Color, 3.f);
		// Arrowhead at the inner end: wind flows toward the boat.
		const FVector2D Dir = (Tail - Tip).GetSafeNormal();
		const FVector2D Side(-Dir.Y, Dir.X);
		DrawLine(Tail.X, Tail.Y, Tail.X - Dir.X * 10.f * UIScale + Side.X * 6.f * UIScale, Tail.Y - Dir.Y * 10.f * UIScale + Side.Y * 6.f * UIScale, Color, 3.f);
		DrawLine(Tail.X, Tail.Y, Tail.X - Dir.X * 10.f * UIScale - Side.X * 6.f * UIScale, Tail.Y - Dir.Y * 10.f * UIScale - Side.Y * 6.f * UIScale, Color, 3.f);
	};
	Arrow(Twa, 0.55f * R, FLinearColor(0.4f, 0.7f, 1.f));
	Arrow(float(T.ApparentWindAngle), 0.4f * R, FLinearColor(1.f, 0.85f, 0.2f));
	Text(TEXT("true"), Center.X - Radius, Center.Y + Radius + 6.f, FLinearColor(0.4f, 0.7f, 1.f), 0.8f);
	Text(TEXT("apparent"), Center.X - Radius + 50.f, Center.Y + Radius + 6.f, FLinearColor(1.f, 0.85f, 0.2f), 0.8f);
}

void ASailingHUD::DrawTips(const ASailboatPawn& Boat)
{
	const FBoatModel& Model = Boat.GetBoatModel();
	const FBoatTelemetry& T = Model.GetTelemetry();
	const FBoatControls& C = Boat.GetControls();
	const double TwaDeg = FMath::RadiansToDegrees(T.TrueWindAngle);
	const double HeelLeeward = FMath::RadiansToDegrees(T.Heel) * Model.GetState().WindwardSide;

	TArray<TPair<FString, FLinearColor>> Tips;
	const FString Pos = PointOfSail(TwaDeg, T.bInIrons);
	Tips.Add({ FString::Printf(TEXT("%s  (%s tack)"), *Pos, TwaDeg >= 0.0 ? TEXT("starboard") : TEXT("port")), FLinearColor::White });

	if (T.bInIrons)
	{
		Tips.Add({ TEXT("Stuck head to wind. Push the tiller toward the boom and hold the jib out to the side the bow should go (backing it)."), Warn });
		Tips.Add({ TEXT("You will drift backward first; the bow falls off, then trim in and sail away."), Dim });
	}
	else if (FMath::Abs(TwaDeg) < 35.0)
	{
		Tips.Add({ TEXT("Too close to the wind: the sails cannot draw. Bear away (steer away from the wind) to about 45 degrees."), Warn });
	}

	auto Count = [](const FSailStripState* Strips, int32 N, ESailFlow Flow) { int32 K = 0; for (int32 I = 0; I < N; ++I) K += Strips[I].Flow == Flow; return K; };
	const int32 JibLuff = Count(T.JibStrips, T.NumJibStrips, ESailFlow::Luffing) + Count(T.JibStrips, T.NumJibStrips, ESailFlow::Backed);
	const int32 JibStall = Count(T.JibStrips, T.NumJibStrips, ESailFlow::Stalled);
	const int32 MainLuff = Count(T.MainStrips, T.NumMainStrips, ESailFlow::Luffing) + Count(T.MainStrips, T.NumMainStrips, ESailFlow::Backed);
	const int32 MainStall = Count(T.MainStrips, T.NumMainStrips, ESailFlow::Stalled);
	const bool bUpwind = FMath::Abs(TwaDeg) < 60.0;

	if (!T.bInIrons && FMath::Abs(TwaDeg) >= 35.0)
	{
		if (JibLuff >= 2)
			Tips.Add({ bUpwind ? TEXT("Jib is luffing (windward telltales lifting): trim the jib in (E), or bear away a little.") : TEXT("Jib is luffing: trim the jib in (E) until the luff stops bubbling."), Warn });
		else if (JibStall >= 2)
			Tips.Add({ TEXT("Jib is stalled (leeward telltales drooping): ease the jib (Q), or head up a little."), Warn });
		else
			Tips.Add({ TEXT("Jib telltales streaming: well trimmed."), Good });

		if (MainLuff >= 2)
			Tips.Add({ TEXT("Main is luffing: trim the mainsheet in (W)."), Warn });
		else if (MainStall >= 2)
			Tips.Add({ TEXT("Main is stalled (leech telltales curling behind the sail): ease the mainsheet (S)."), Warn });
		else
			Tips.Add({ TEXT("Main leech telltales streaming: well trimmed."), Good });
	}

	if (HeelLeeward > 22.0)
		Tips.Add({ USailingSettings::Get()->UseSimpleControls() ? TEXT("Heeling too much: hike out (F) and ease the main (S) in the puffs.")
			: TEXT("Heeling too much: hike out (F), ease the main or drop the traveler (C), flatten with backstay (8)."), Bad });
	else if (HeelLeeward > 12.0 && C.Hike < 0.8)
		Tips.Add({ TEXT("Building breeze: get the crew hiking (F)."), Dim });
	if (T.HelmForce > 40.0)
		Tips.Add({ TEXT("Heavy weather helm: the boat wants to round up. Ease the main to balance her."), Warn });
	if (const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>())
	{
		const FWeatherState& W = GM->GetWeatherState();
		if (W.Storm == EStormPhase::Building)
			Tips.Add({ TEXT("Thunderstorm building to the west-northwest: watch for the dark line of the gust front on the water and reef or head in."), Bad });
		else if (W.Storm == EStormPhase::GustFront || W.Storm == EStormPhase::Rain)
			Tips.Add({ TEXT("Storm: depower (ease sheets, hike), keep the bow off the wind, and stay clear of the mast in lightning."), Bad });
	}
	if (FMath::Abs(TwaDeg) > 160.0 && !C.bWingOnWing)
		Tips.Add({ TEXT("Dead downwind: try wing-on-wing (G), jib out on the opposite side. Watch for an accidental gybe."), Dim });
	if (FMath::Abs(TwaDeg) > 170.0)
		Tips.Add({ TEXT("Sailing by the lee risks an accidental gybe: steer a few degrees toward the wind."), Warn });

	const float X = Canvas->ClipX / UIScale * 0.5f - 330.f;
	float Y = 18.f;
	DrawRect(Panel, X * UIScale, 10.f * UIScale, 660.f * UIScale, (Tips.Num() * 24.f + 16.f) * UIScale);
	for (const TPair<FString, FLinearColor>& Tip : Tips)
	{
		Text(Tip.Key, X + 12.f, Y, Tip.Value, 0.85f);
		Y += 24.f;
	}
}
