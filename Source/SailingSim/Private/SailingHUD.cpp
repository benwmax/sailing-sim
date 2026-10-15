#include "SailingHUD.h"
#include "Learning.h"
#include "SailingSim.h"
#include "SailSession.h"
#include "UI/SailFrontEnd.h"
#include "UI/SailLoading.h"
#include "UI/SailHud.h"
#include "Engine/GameViewportClient.h"
#include "Framework/Application/SlateApplication.h"
#include "Kismet/GameplayStatics.h"
#include "SailboatPawn.h"
#include "SailingSettings.h"
#include "SailingGameMode.h"
#include "Weather.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Misc/Paths.h"
#include "CanvasItem.h"
#include "Chart.h"
#include "Navigation.h"
#include "Tides.h"
#include "TrafficManager.h"

using namespace Sailing;

namespace SailingHUDLocal
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
	using namespace SailingHUDLocal;
	UFont* Font = bBig ? GEngine->GetLargeFont() : GEngine->GetMediumFont();
	DrawText(Str, Color, X * UIScale, Y * UIScale, Font, Scale * UIScale);
}

void ASailingHUD::Bar(const FString& Label, float Value, float Lo, float Hi, float X, float Y, float Width, const FLinearColor& Color)
{
	using namespace SailingHUDLocal;
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

ASailingHUD::ASailingHUD()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bTickEvenWhenPaused = true;   // the scripted menu check runs through Pause too
}

bool ASailingHUD::UsesFrontEnd() const
{
	using namespace SailingHUDLocal;
	static const bool bOff = GIsAutomationTesting || FParse::Param(FCommandLine::Get(), TEXT("SailingNoFrontEnd")) || FParse::Param(FCommandLine::Get(), TEXT("SailingDemo"))
		|| FCommandLine::Get() && (FString(FCommandLine::Get()).Contains(TEXT("SailingBench=")) || FString(FCommandLine::Get()).Contains(TEXT("SailingCapture="))
			|| FString(FCommandLine::Get()).Contains(TEXT("SailingShot=")) || FString(FCommandLine::Get()).Contains(TEXT("SailingDrill=")))
		|| FParse::Param(FCommandLine::Get(), TEXT("SailingMenu")) || IsRunningCommandlet();
	FString Forced;   // -SailingFrontEnd=<screen> forces it (screenshots of the menus)
	return !bOff || FParse::Value(FCommandLine::Get(), TEXT("SailingFrontEnd="), Forced);
}

void ASailingHUD::BeginPlay()
{
	using namespace SailingHUDLocal;
	Super::BeginPlay();
	if (PlayerOwner && GEngine && GEngine->GameViewport && !IsRunningCommandlet())
	{
		SlateHud = SNew(SSailHud).Player(PlayerOwner);
		GEngine->GameViewport->AddViewportWidgetContent(SlateHud.ToSharedRef(), 5);
	}
	if (!UsesFrontEnd() || !PlayerOwner) return;
	USailSessionSubsystem* Session = USailSessionSubsystem::Get(this);
	FString Screen;
	// A session that has just loaded goes to its loading screen, whatever screen the command line asked for first.
	const bool bLoadingSession = Session && Session->bHasActive && !Session->bStarted && Session->Active.SavedAt > FDateTime::MinValue()
		&& (FDateTime::Now() - Session->Active.SavedAt).GetTotalMinutes() < 10.0;
	if (!bLoadingSession && FParse::Value(FCommandLine::Get(), TEXT("SailingFrontEnd="), Screen))
	{
		// Screenshots of each screen: -SailingFrontEnd=World|Launch|Boat|Conditions|Mode|Pause|Settings|Controls|Loading.
		if (Screen == TEXT("Briefing") || Screen == TEXT("Quiz"))
		{
			// Graphics G7 stills: the drill's briefing or its quiz a few seconds in (with -SailingDrill=<name>).
			bLearningScreensAuto = false;
			FTimerHandle Later;
			const ESailScreen Learn = Screen == TEXT("Briefing") ? ESailScreen::Briefing : ESailScreen::Quiz;
			GetWorldTimerManager().SetTimer(Later, FTimerDelegate::CreateWeakLambda(this, [this, Learn]() { OpenLearning(Learn); }), 4.f, false);
			return;
		}
		if (Screen == TEXT("Loading"))
		{
			if (Session && !Session->bHasActive) { Session->Active = USailSessionSubsystem::MakeDefault(); Session->bHasActive = true; }
			Session->bStarted = false;
		}
		else
		{
			static const TCHAR* Names[] = { TEXT("Title"), TEXT("World"), TEXT("Launch"), TEXT("Boat"), TEXT("Conditions"), TEXT("Mode"), TEXT("Pause"), TEXT("ConditionsInGame"), TEXT("Settings"), TEXT("Controls") };
			for (int32 I = 0; I < UE_ARRAY_COUNT(Names); ++I)
			{
				if (Screen == Names[I])
				{
					OpenFrontEnd(ESailScreen::Title);
					if (I > 0 && I != int32(ESailScreen::Pause))
					{
						// Walk the flow to it, so Back works as it would.
						for (int32 K = 1; K <= I && K <= int32(ESailScreen::Mode); ++K) FrontEnd->Push(ESailScreen(K));
						if (I > int32(ESailScreen::Mode)) FrontEnd->Push(ESailScreen(I));
					}
					else if (I == int32(ESailScreen::Pause))
					{
						// Paused a few seconds in, once the camera has settled behind the boat.
						CloseFrontEnd();
						FTimerHandle Later;
						GetWorldTimerManager().SetTimer(Later, FTimerDelegate::CreateUObject(this, &ASailingHUD::OpenPause), 4.f, false);
					}
					return;
				}
			}
		}
	}
	if (Session && Session->bHasActive && !Session->bStarted)
	{
		// A session just loaded: the loading screen until the world is ready and the player says go.
		if (ASailboatPawn* Pawn = Cast<ASailboatPawn>(PlayerOwner->GetPawn())) Pawn->SetHeldByUI(true);
		Loading = SNew(SSailLoading).World(GetWorld()).OnStart(FSimpleDelegate::CreateUObject(this, &ASailingHUD::StartSailing));
		ShowWidget(Loading.ToSharedRef(), Loading);
	}
	else if (!Session || !Session->bHasActive)
	{
		OpenFrontEnd(ESailScreen::Title);
	}
}

void ASailingHUD::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	WatchDrill();
	USailSessionSubsystem* Session = USailSessionSubsystem::Get(this);
	if (!Session) return;
	if (!Session->bUIScriptRead)
	{
		Session->bUIScriptRead = true;
		FString Script;
		if (FParse::Value(FCommandLine::Get(), TEXT("SailingUIScript="), Script, false)) Script.ParseIntoArray(Session->UIScript, TEXT(","));
		NextScriptKey = FPlatformTime::Seconds() + 4.0;
	}
	if (Session->UIScript.Num() == 0 || FPlatformTime::Seconds() < NextScriptKey) return;
	NextScriptKey = FPlatformTime::Seconds() + 0.6;
	const FString Token = Session->UIScript[0];
	Session->UIScript.RemoveAt(0);
	if (Token == TEXT("Wait")) { NextScriptKey += 2.0; return; }
	if (Token == TEXT("Log"))
	{
		const USailingSettings* S = USailingSettings::Get();
		FString Stage = TEXT("-");
		const float Progress = Loading.IsValid() ? Loading->Progress(Stage) : 1.f;
		UE_LOG(LogSailing, Display, TEXT("UI script: world %d, launch %d, boat %d, preset %d, hour %.2f, traffic %d, front end %s, loading %.0f%% (%s)"),
			S->World, S->LaunchSpot, S->BoatType, int32(S->WeatherPreset), S->StartHour, S->TrafficLevel, IsFrontEndOpen() ? TEXT("open") : TEXT("closed"), Progress * 100.f, *Stage);
		return;
	}
	const FKey Key(*Token);
	if (!Key.IsValid()) return;
	FSlateApplication& App = FSlateApplication::Get();
	const FKeyEvent Down(Key, FModifierKeysState(), 0, false, 0, 0);
	const TSharedPtr<SWidget> Focused = App.GetUserFocusedWidget(0);
	const bool bHandled = App.ProcessKeyDownEvent(Down);
	UE_LOG(LogSailing, Display, TEXT("UI script: %s -> %s (%s)"), *Token, Focused.IsValid() ? *Focused->GetTypeAsString() : TEXT("nothing"), bHandled ? TEXT("handled") : TEXT("unhandled"));
	App.ProcessKeyUpEvent(FKeyEvent(Key, FModifierKeysState(), 0, false, 0, 0));
}

void ASailingHUD::EndPlay(const EEndPlayReason::Type Reason)
{
	using namespace SailingHUDLocal;
	RemoveWidgets();
	if (SlateHud.IsValid() && GEngine && GEngine->GameViewport) GEngine->GameViewport->RemoveViewportWidgetContent(SlateHud.ToSharedRef());
	SlateHud.Reset();
	Super::EndPlay(Reason);
}

void ASailingHUD::ShowWidget(TSharedRef<SWidget> Widget, TSharedPtr<SWidget> Focus)
{
	using namespace SailingHUDLocal;
	RemoveWidgets();
	if (!GEngine || !GEngine->GameViewport) return;
	GEngine->GameViewport->AddViewportWidgetContent(Widget, 50);
	ShownWidget = Widget;
	PlayerOwner->SetShowMouseCursor(true);
	FInputModeUIOnly Mode;
	Mode.SetWidgetToFocus(Focus);
	Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
	PlayerOwner->SetInputMode(Mode);
}

void ASailingHUD::RemoveWidgets()
{
	using namespace SailingHUDLocal;
	if (ShownWidget.IsValid() && GEngine && GEngine->GameViewport) GEngine->GameViewport->RemoveViewportWidgetContent(ShownWidget.ToSharedRef());
	ShownWidget.Reset();
}

void ASailingHUD::OpenFrontEnd(ESailScreen Screen)
{
	using namespace SailingHUDLocal;
	if (ASailboatPawn* Pawn = Cast<ASailboatPawn>(PlayerOwner->GetPawn()); Pawn && Screen != ESailScreen::Pause) Pawn->SetHeldByUI(true);
	Loading.Reset();
	FrontEnd = SNew(SSailFrontEnd).Start(Screen).Player(PlayerOwner).OnClose(FSimpleDelegate::CreateUObject(this, &ASailingHUD::CloseFrontEnd));
	ShowWidget(FrontEnd.ToSharedRef(), FrontEnd);
	FrontEnd->FocusCurrent();
}

void ASailingHUD::OpenPause()
{
	using namespace SailingHUDLocal;
	if (IsFrontEndOpen()) return;
	UGameplayStatics::SetGamePaused(this, true);
	bPausedByMenu = true;
	OpenFrontEnd(ESailScreen::Pause);
}

void ASailingHUD::OpenLearning(ESailScreen Screen)
{
	using namespace SailingHUDLocal;
	if (IsFrontEndOpen()) return;
	UGameplayStatics::SetGamePaused(this, true);
	bPausedByMenu = true;
	OpenFrontEnd(Screen);
}

void ASailingHUD::WatchDrill()
{
	using namespace SailingHUDLocal;
	// Graphics G7: in learning mode, the briefing when a drill starts and a short quiz a few seconds after it ends.
	ASailboatPawn* Pawn = PlayerOwner ? Cast<ASailboatPawn>(PlayerOwner->GetPawn()) : nullptr;
	if (!Pawn || !bLearningScreensAuto || !UsesFrontEnd() || IsFrontEndOpen()) return;
	const bool bLearning = USailingSettings::Get()->bLearningMode;
	const FDrillRunner& D = Pawn->GetDrill();
	const int32 Serial = Pawn->GetDrillSerial();
	if (Serial != BriefedSerial)
	{
		BriefedSerial = Serial;
		DrillDoneAt = -1.0;
		if (bLearning && D.IsActive() && FLearningContent::Get().Briefing(D.GetDrill())) OpenLearning(ESailScreen::Briefing);
		return;
	}
	if (!D.IsComplete() || QuizzedSerial == Serial) return;
	const double Now = FPlatformTime::Seconds();
	if (DrillDoneAt < 0.0) DrillDoneAt = Now;
	if (Now - DrillDoneAt < 3.0) return;
	QuizzedSerial = Serial;
	DrillDoneAt = -1.0;
	if (bLearning && FLearningContent::Get().Briefing(D.GetDrill())) OpenLearning(ESailScreen::Quiz);
}

void ASailingHUD::CloseFrontEnd()
{
	using namespace SailingHUDLocal;
	RemoveWidgets();
	FrontEnd.Reset();
	Loading.Reset();
	if (bPausedByMenu) { UGameplayStatics::SetGamePaused(this, false); bPausedByMenu = false; }
	if (ASailboatPawn* Pawn = Cast<ASailboatPawn>(PlayerOwner->GetPawn())) Pawn->SetHeldByUI(false);
	PlayerOwner->SetShowMouseCursor(false);
	PlayerOwner->SetInputMode(FInputModeGameOnly());
	FSlateApplication::Get().SetAllUserFocusToGameViewport();
}

void ASailingHUD::StartSailing()
{
	using namespace SailingHUDLocal;
	if (USailSessionSubsystem* Session = USailSessionSubsystem::Get(this)) Session->bStarted = true;
	CloseFrontEnd();
}

void ASailingHUD::DrawHUD()
{
	using namespace SailingHUDLocal;
	Super::DrawHUD();
	if (IsFrontEndOpen()) return;   // the menus own the screen
	const ASailboatPawn* Boat = PlayerOwner ? Cast<ASailboatPawn>(PlayerOwner->GetPawn()) : nullptr;
	if (!Boat || !Canvas)
	{
		return;
	}
	UIScale = FMath::Clamp(Canvas->ClipY / 1080.f, 0.7f, 2.f);

	const USailingSettings* Settings = USailingSettings::Get();
	if (Boat->IsCaptureMode()) return; // reference captures: the picture only
	if (Boat->IsPhotoMode())
	{
		// Nothing over the picture but a moment's hint.
		if (FPlatformTime::Seconds() < Boat->GetPhotoHintUntil())
		{
			const FString Msg = Boat->GetStatusMessage();
			Text(Msg.IsEmpty() ? FString(TEXT("Photo mode: mouse orbits, wheel moves in and out, [ ] lens, Enter takes a photo, 9 leaves")) : Msg,
				20.f, Canvas->ClipY / UIScale - 40.f, FLinearColor::White, 0.8f);
		}
		return;
	}
	if (Boat->IsWatching())
	{
		const FReplay& Run = Boat->GetLastRun();
		const float W = 760.f, X = Canvas->ClipX / UIScale * 0.5f - W * 0.5f, Y = Canvas->ClipY / UIScale - 110.f;
		DrawRect(Panel, X * UIScale, Y * UIScale, W * UIScale, 90.f * UIScale);
		const double T = Boat->GetWatchTime(), D = Run.Duration();
		Text(FString::Printf(TEXT("Replay: %s   %d:%02d / %d:%02d   x%g"), *Run.Label, int32(T) / 60, int32(T) % 60, int32(D) / 60, int32(D) % 60, Boat->GetWatchSpeed()),
			X + 14.f, Y + 10.f, FLinearColor::White, 0.95f);
		DrawRect(FLinearColor(1, 1, 1, 0.2f), (X + 14.f) * UIScale, (Y + 42.f) * UIScale, (W - 28.f) * UIScale, 6.f * UIScale);
		DrawRect(Good, (X + 14.f) * UIScale, (Y + 42.f) * UIScale, float((W - 28.f) * (D > 0.0 ? T / D : 0.0)) * UIScale, 6.f * UIScale);
		Text(TEXT("Left / Right skip 10 s, Up / Down speed, mouse orbits, wheel zooms, comma returns to your boat"), X + 14.f, Y + 58.f, Dim, 0.75f);
		return;
	}
	if (Boat->IsKeysOpen())
	{
		DrawKeys(*Boat);
		return;
	}
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
	if (Boat->IsChartOpen())
	{
		DrawChart(*Boat);
		return;
	}
	if (Boat->IsLogOpen())
	{
		DrawLogbook(*Boat);
		return;
	}
	if (!Settings->bShowHud)
	{
		// Clean stills (-SailingNoHud) get no hint line either.
		static const bool bNoHud = FParse::Param(FCommandLine::Get(), TEXT("SailingNoHud"));
		if (!bNoHud && !SlateHud.IsValid()) Text(TEXT("H: show instruments   ?: controls   Tab: settings"), 20.f, 20.f, Dim, 0.8f);
		return;
	}
	if (SlateHud.IsValid())
	{
		// Graphics G4: the Slate HUD (UI/SailHud.h) draws everything the canvas did: instruments, tips, drill, race,
		// rules callouts and the coast's navigation.
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
	DrawNavigation(*Boat, Settings->bLearningMode ? 300.f : 10.f);
	DrawTraffic(*Boat);
}

void ASailingHUD::DrawKeys(const ASailboatPawn& Boat)
{
	using namespace SailingHUDLocal;
	const TArray<ASailboatPawn::FKeyRow>& Rows = Boat.GetKeyRows();
	const float RowH = 24.f;
	const int32 PerColumn = FMath::Max(1, int32((Canvas->ClipY / UIScale - 200.f) / RowH));
	const int32 Columns = (Rows.Num() + PerColumn - 1) / PerColumn;
	const float ColW = 470.f, W = FMath::Max(1, Columns) * ColW + 40.f, H = FMath::Min(Rows.Num(), PerColumn) * RowH + 140.f;
	const float X = Canvas->ClipX / UIScale * 0.5f - W * 0.5f, Y = Canvas->ClipY / UIScale * 0.5f - H * 0.5f;
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.78f), X * UIScale, Y * UIScale, W * UIScale, H * UIScale);
	Text(TEXT("Keys"), X + 20.f, Y + 14.f, FLinearColor::White, 1.1f, true);
	for (int32 I = 0; I < Rows.Num(); ++I)
	{
		const float CX = X + 20.f + (I / PerColumn) * ColW, RY = Y + 60.f + (I % PerColumn) * RowH;
		const bool bSel = I == Boat.GetKeysIndex();
		if (bSel) DrawRect(FLinearColor(0.3f, 0.5f, 0.8f, 0.5f), (CX - 6.f) * UIScale, (RY - 3.f) * UIScale, (ColW - 20.f) * UIScale, RowH * UIScale);
		Text(Rows[I].Label, CX, RY, bSel ? FLinearColor::White : Dim, 0.78f);
		Text(bSel && Boat.IsCapturingKey() ? FString(TEXT("...")) : Rows[I].Key.GetDisplayName().ToString(), CX + 330.f, RY, bSel ? Good : FLinearColor::White, 0.78f);
	}
	Text(Boat.GetKeysMessage(), X + 20.f, Y + H - 56.f, Boat.IsCapturingKey() ? Warn : Dim, 0.8f);
	Text(TEXT("Saved to your Input.ini. Mouse and controller bindings are unchanged."), X + 20.f, Y + H - 30.f, Dim, 0.7f);
}

void ASailingHUD::DrawLogbook(const ASailboatPawn& Boat)
{
	using namespace SailingHUDLocal;
	const FLogbook& Log = Boat.GetLogbook();
	const float W = 1240.f, H = Canvas->ClipY / UIScale - 80.f;
	const float X = Canvas->ClipX / UIScale * 0.5f - W * 0.5f, Y = 40.f;
	// Paper and ink.
	DrawRect(FLinearColor(0.72f, 0.68f, 0.56f, 1.f), X * UIScale, Y * UIScale, W * UIScale, H * UIScale);
	const FLinearColor Ink(0.f, 0.f, 0.02f), Faint(0.12f, 0.11f, 0.09f), Red(0.45f, 0.02f, 0.01f);
	Text(FString::Printf(TEXT("Ship's log: %s, %s"), *Log.GetBoat(), *Log.GetArea()), X + 20.f, Y + 12.f, Ink, 1.05f, true);
	const TArray<FLogEntry>& E = Log.GetEntries();
	const double Hours = E.Num() > 0 ? (E.Last().UnixTime - Log.SessionStartUnix) / 3600.0 : 0.0;
	Text(FString::Printf(TEXT("%.1f nm by the log in %.1f h; best speed %.1f kn. Saved to %s"), E.Num() ? E.Last().LogNm : 0.0, Hours, Log.MaxSpeedKnots,
		*FPaths::GetCleanFilename(Log.GetFilePath())), X + 20.f, Y + 48.f, Faint, 0.72f);
	const float Cols[] = { 20.f, 90.f, 340.f, 420.f, 490.f, 560.f, 640.f, 760.f, 830.f };
	const TCHAR* Heads[] = { TEXT("Time"), TEXT("Position"), TEXT("Course"), TEXT("Speed"), TEXT("Hdg M"), TEXT("Log nm"), TEXT("Wind"), TEXT("Sea"), TEXT("Remarks") };
	float RY = Y + 78.f;
	for (int32 I = 0; I < UE_ARRAY_COUNT(Cols); ++I) Text(Heads[I], X + Cols[I], RY, Faint, 0.75f);
	RY += 26.f;
	const int32 Rows = FMath::Max(1, int32((H - 130.f) / 22.f));
	for (int32 I = FMath::Max(0, E.Num() - Rows); I < E.Num(); ++I)
	{
		const FLogEntry& L = E[I];
		const FLinearColor C = L.Kind == TEXT("Watch") ? Ink : Red;
		Text(L.Clock, X + Cols[0], RY, C, 0.72f);
		Text(FLogbook::FormatPosition(L.Latitude, L.Longitude), X + Cols[1], RY, C, 0.72f);
		Text(FString::Printf(TEXT("%03.0f T"), L.CourseTrue), X + Cols[2], RY, C, 0.72f);
		Text(FString::Printf(TEXT("%.1f"), L.SpeedKnots), X + Cols[3], RY, C, 0.72f);
		Text(FString::Printf(TEXT("%03.0f"), L.HeadingMagnetic), X + Cols[4], RY, C, 0.72f);
		Text(FString::Printf(TEXT("%.1f"), L.LogNm), X + Cols[5], RY, C, 0.72f);
		Text(FString::Printf(TEXT("%03.0f %.0f kn"), L.WindFromDeg, L.WindKnots), X + Cols[6], RY, C, 0.72f);
		Text(FString::Printf(TEXT("%.1f m"), L.SeaMeters), X + Cols[7], RY, C, 0.72f);
		Text(L.Remarks.IsEmpty() ? FString(TEXT("Watch")) : L.Remarks, X + Cols[8], RY, C, 0.72f);
		RY += 22.f;
	}
	Text(TEXT("Y closes the log"), X + 20.f, Y + H - 28.f, Faint, 0.7f);
}

void ASailingHUD::DrawTraffic(const ASailboatPawn& Boat)
{
	using namespace SailingHUDLocal;
	const ATrafficManager* TM = ATrafficManager::Find(GetWorld());
	if (!TM) return;
	const USailingSettings* Settings = USailingSettings::Get();
	const double Now = TM->GetSim().GetTime();
	const float CX = Canvas->ClipX / UIScale * 0.5f, Bottom = Canvas->ClipY / UIScale;
	const FRulesCoach& Coach = TM->GetCoach();
	float Y = Bottom - 140.f;

	// Learning: what the rules say about the vessel that matters most right now.
	const FRulesCoach::FAdvice& A = Coach.GetAdvice();
	if (Settings->bLearningMode && A.bActive)
	{
		const float W = 700.f, H = 118.f;
		Y = Bottom - 150.f - H;
		DrawRect(Panel, (CX - W * 0.5f) * UIScale, Y * UIScale, W * UIScale, H * UIScale);
		const FLinearColor RoleColour = A.bGiveWay ? Warn : (A.bStandOn ? Good : Dim);
		Text(UTF8_TO_TCHAR(A.Who.c_str()), CX - W * 0.5f + 12.f, Y + 8.f, FLinearColor::White, 0.85f);
		Text(FString::Printf(TEXT("%s  (%s)"), UTF8_TO_TCHAR(A.Role.c_str()), UTF8_TO_TCHAR(A.Rule.c_str())), CX - W * 0.5f + 12.f, Y + 30.f, RoleColour, 0.95f);
		Text(UTF8_TO_TCHAR(A.Reason.c_str()), CX - W * 0.5f + 12.f, Y + 54.f, Dim, 0.72f);
		Text(UTF8_TO_TCHAR(A.Action.c_str()), CX - W * 0.5f + 12.f, Y + 74.f, FLinearColor::White, 0.75f);
		if (A.Tcpa > 0.0 && A.Tcpa < 900.0)
		{
			Text(FString::Printf(TEXT("Closest approach %.0f m in %.0f s"), A.Cpa, A.Tcpa), CX - W * 0.5f + 12.f, Y + 96.f, A.Cpa < 30.0 ? Bad : Dim, 0.72f);
		}
	}
	// Game mode: the rules score and the latest judgment.
	if (!Settings->bLearningMode || !Coach.GetScores().empty())
	{
		const std::vector<FRulesCoach::FScore>& Scores = Coach.GetScores();
		if (!Settings->bLearningMode)
		{
			Text(FString::Printf(TEXT("Rules score %+d"), Coach.GetScore()), CX - 70.f, 14.f, Coach.GetScore() < 0 ? Bad : Good, 0.95f);
		}
		if (!Scores.empty() && Now - Scores.back().Time < 8.0)
		{
			const FRulesCoach::FScore& Last = Scores.back();
			Text(FString::Printf(TEXT("%+d  %s"), Last.Points, UTF8_TO_TCHAR(Last.Text.c_str())), CX - 330.f, Y - 26.f, Last.Points < 0 ? Bad : Good, 0.8f);
		}
	}
	// Signals heard and vessels keeping clear: the last few seconds.
	float MY = Y - 52.f;
	const TArray<TPair<double, FString>>& Messages = TM->GetMessages();
	for (int32 I = Messages.Num() - 1, Shown = 0; I >= 0 && Shown < 3; --I)
	{
		if (Now - Messages[I].Key > 8.0) break;
		Text(Messages[I].Value, CX - 330.f, MY, FLinearColor(0.85f, 0.9f, 1.f), 0.75f);
		MY -= 22.f;
		++Shown;
	}

	// The race.
	const FRaceRunner* R = TM->GetRace();
	if (!R) return;
	const FRaceEntry* Me = R->FindEntry(FTrafficSim::PlayerId);
	const float X = 10.f, Top = 300.f, W = 330.f;
	const int32 Rows = R->IsOver() ? int32(R->Entries.size()) : 0;
	DrawRect(Panel, X * UIScale, Top * UIScale, W * UIScale, (104.f + Rows * 22.f) * UIScale);
	const double ToStart = R->StartTime() - Now;
	FString Head;
	FLinearColor HeadColour = FLinearColor::White;
	switch (R->Phase(Now))
	{
	case FRaceRunner::EPhase::Warning: Head = FString::Printf(TEXT("Start in %d:%02d   class flag up"), int32(ToStart) / 60, int32(ToStart) % 60); break;
	case FRaceRunner::EPhase::Preparatory: Head = FString::Printf(TEXT("Start in %d:%02d   class flag + P flag"), int32(ToStart) / 60, int32(ToStart) % 60); HeadColour = Warn; break;
	case FRaceRunner::EPhase::OneMinute: Head = FString::Printf(TEXT("Start in 0:%02d   P flag down"), int32(ToStart)); HeadColour = Bad; break;
	case FRaceRunner::EPhase::Racing: Head = FString::Printf(TEXT("Racing %d:%02d   position %d of %d"), int32(-ToStart) / 60, int32(-ToStart) % 60, TM->GetRacePosition(), int32(R->Entries.size())); HeadColour = Good; break;
	default: Head = TEXT("Race over: results"); break;
	}
	Text(Head, X + 12.f, Top + 8.f, HeadColour, 0.95f);
	if (Me)
	{
		Text(UTF8_TO_TCHAR(R->NextTask(*Me).c_str()), X + 12.f, Top + 34.f, Me->bOcs ? Bad : FLinearColor::White, 0.78f);
		// How far to the line (before the start) or to the next mark.
		const FVector2D P = Boat.GetMapPosition();
		if (!Me->bStarted || Me->bOcs)
		{
			Text(FString::Printf(TEXT("Line: %.0f m %s"), FMath::Abs(R->Course.CourseSide(P.X, P.Y)), R->Course.CourseSide(P.X, P.Y) > 0.0 ? TEXT("over (on the course side)") : TEXT("below")),
				X + 12.f, Top + 58.f, R->Course.CourseSide(P.X, P.Y) > 0.0 ? Bad : Dim, 0.75f);
		}
		else if (Me->NextMark < int32(R->Course.Marks.size()))
		{
			const FRaceMark& M = R->Course.Marks[Me->NextMark];
			const double Brg = SailingNav::BearingDeg(P, FVector2D(M.X, M.Y));
			Text(FString::Printf(TEXT("%s: %.0f m, bearing %03.0f"), UTF8_TO_TCHAR(M.Name.c_str()), FVector2D::Distance(P, FVector2D(M.X, M.Y)), Brg), X + 12.f, Top + 58.f, Dim, 0.75f);
		}
	}
	Text(TEXT("Tab > Race: Left ends the race"), X + 12.f, Top + 80.f, Dim, 0.65f);
	if (R->IsOver())
	{
		TArray<const FRaceEntry*> Sorted;
		for (const FRaceEntry& E : R->Entries) Sorted.Add(&E);
		Sorted.Sort([](const FRaceEntry& A2, const FRaceEntry& B2) { return A2.Points < B2.Points; });
		for (int32 I = 0; I < Sorted.Num(); ++I)
		{
			const FRaceEntry& E = *Sorted[I];
			const FString Line = E.bFinished ? FString::Printf(TEXT("%d. %s  %d:%02d  %d pt"), E.Place, UTF8_TO_TCHAR(E.Name.c_str()), int32(E.FinishTime - R->StartTime()) / 60, int32(E.FinishTime - R->StartTime()) % 60, E.Points)
				: FString::Printf(TEXT("-  %s  %s  %d pt"), UTF8_TO_TCHAR(E.Name.c_str()), UTF8_TO_TCHAR(E.Status.c_str()), E.Points);
			Text(Line, X + 12.f, Top + 104.f + I * 22.f, E.VesselId == FTrafficSim::PlayerId ? Good : FLinearColor::White, 0.78f);
		}
	}
}

void ASailingHUD::DrawNavigation(const ASailboatPawn& Boat, float Top)
{
	using namespace SailingHUDLocal;
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM || !GM->GetLake().IsTidal()) return;
	const FLakeData& Lake = GM->GetLake();
	const FBoatModel& Model = Boat.GetBoatModel();
	const FBoatTelemetry& T = Model.GetTelemetry();
	const float W = 270.f, X = Canvas->ClipX / UIScale - W - 10.f;
	const TArray<TPair<FString, FVector2D>>& Plan = Lake.Passage;
	const bool bPassage = Boat.GetPassageIndex() >= 0 && Boat.GetPassageIndex() < Plan.Num();
	DrawRect(Panel, X * UIScale, Top * UIScale, W * UIScale, (bPassage ? 222.f : 196.f) * UIScale);
	float Y = Top + 8.f;
	const double HeadingT = Boat.GetHeadingTrueDeg();
	Text(FString::Printf(TEXT("Compass  %03.0f M"), SailingNav::TrueToMagnetic(HeadingT, Lake.VariationDeg)), X + 12.f, Y, FLinearColor::White, 1.f);
	Y += 24.f;
	// The depth sounder reads from the transducer (about 0.3 m down) to the bottom, in feet as the chart is.
	const double Depth = T.DepthUnderKeel + Model.GetConfig().Draft - 0.3;
	Text(FString::Printf(TEXT("Depth    %.1f ft"), Depth / 0.3048), X + 12.f, Y, T.DepthUnderKeel < 1.0 ? Warn : FLinearColor::White, 1.f);
	Y += 24.f;
	Text(FString::Printf(TEXT("Log      %.1f kn"), T.SpeedThroughWater / kKnot), X + 12.f, Y, FLinearColor::White, 1.f);
	Y += 24.f;
	const Vec3 V = Model.GetState().Velocity;
	const double Sog = FMath::Sqrt(V.X * V.X + V.Y * V.Y);
	if (Boat.IsGpsShown())
	{
		const double Cog = SailingNav::NormalizeDeg(FMath::RadiansToDegrees(FMath::Atan2(V.Y, V.X)));
		Text(FString::Printf(TEXT("GPS      %.1f kn  %03.0f T"), Sog / kKnot, Sog > 0.1 ? Cog : HeadingT), X + 12.f, Y, Dim, 0.9f);
	}
	else
	{
		Text(TEXT("GPS      off (O)"), X + 12.f, Y, Dim, 0.9f);
	}
	Y += 24.f;
	// Tide: height above chart datum (MLLW) and the next turn, in local time.
	FTideEvent Next;
	FString TideLine = FString::Printf(TEXT("Tide     %+.1f ft"), GM->GetTideHeight() / 0.3048);
	if (GM->GetNextTide(Next))
	{
		const double Local = Next.Time + GM->GetUtcOffsetHours() * 3600.0;
		const int32 Minutes = int32(FMath::Fmod(Local / 60.0, 1440.0));
		TideLine += FString::Printf(TEXT("  %s %02d:%02d"), Next.Type == FTideEvent::High ? TEXT("HW") : TEXT("LW"), Minutes / 60, Minutes % 60);
	}
	Text(TideLine, X + 12.f, Y, FLinearColor::White, 0.9f);
	Y += 24.f;
	const Vec3 Cur = GM->GetCurrentAt(Model.OriginPosition().X, Model.OriginPosition().Y);
	const double Set = SailingNav::NormalizeDeg(FMath::RadiansToDegrees(FMath::Atan2(Cur.Y, Cur.X)));
	const double Drift = FMath::Sqrt(Cur.X * Cur.X + Cur.Y * Cur.Y);
	Text(Drift < 0.03 ? FString(TEXT("Current  slack")) : FString::Printf(TEXT("Current  %.1f kn setting %03.0f T"), Drift / kKnot, Set), X + 12.f, Y, Dim, 0.9f);
	Y += 24.f;
	if (bPassage)
	{
		// The passage plan: the next waypoint by GPS, bearing in degrees magnetic, and time at the speed made good.
		const TPair<FString, FVector2D>& Waypoint = Plan[Boat.GetPassageIndex()];
		const FVector2D Here = Boat.GetMapPosition();
		const double Dist = FVector2D::Distance(Here, Waypoint.Value);
		const double Brg = SailingNav::TrueToMagnetic(SailingNav::BearingDeg(Here, Waypoint.Value), Lake.VariationDeg);
		Text(FString::Printf(TEXT("Next   %s %s %03.0f M%s"), *Waypoint.Key, *SailingNav::FormatDistance(Dist), Brg,
			Sog > 0.5 ? *FString::Printf(TEXT("  %.0f min"), Dist / Sog / 60.0) : TEXT("")), X + 12.f, Y, Warn, 0.72f);
		Y += 24.f;
	}
	Text(TEXT("P chart   U bearing   O GPS   Y log"), X + 12.f, Y + 2.f, Dim, 0.75f);
}

void ASailingHUD::DrawChart(const ASailboatPawn& Boat)
{
	using namespace SailingHUDLocal;
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM) return;
	const FChartData& Chart = GM->GetChart();
	const FLakeData& Lake = GM->GetLake();
	const SailingNav::FPlot& Plot = Boat.GetPlot();
	const double Var = Lake.VariationDeg;
	const float SW = Canvas->ClipX, SH = Canvas->ClipY;
	const FVector2D Center = Boat.GetChartCenter();
	const double Mpp = Boat.GetChartMetersPerPixel() / UIScale; // meters per screen pixel
	auto ToScreen = [&](const FVector2D& P) { return FVector2D(SW * 0.5 + (P.Y - Center.Y) / Mpp, SH * 0.5 - (P.X - Center.X) / Mpp); };
	const FBox2D View(FVector2D(Center.X - SH * 0.5 * Mpp, Center.Y - SW * 0.5 * Mpp), FVector2D(Center.X + SH * 0.5 * Mpp, Center.Y + SW * 0.5 * Mpp));
	auto Visible = [&](const FBox2D& B) { return B.bIsValid && B.Intersect(View); };
	const FLinearColor Ink(0.08f, 0.08f, 0.1f), Magenta = FLinearColor::FromSRGBColor(FColor(200, 30, 140)), ContourInk = FLinearColor::FromSRGBColor(FColor(70, 110, 160));

	// Paper: white inside the chart's coverage (dredged channels, not depth areas in the ENC, print white), grey beyond.
	DrawRect(FLinearColor(0.6f, 0.6f, 0.6f), 0.f, 0.f, SW, SH);
	if (Chart.Bounds.bIsValid)
	{
		const FVector2D A = ToScreen(FVector2D(Chart.Bounds.Max.X, Chart.Bounds.Min.Y)), B = ToScreen(FVector2D(Chart.Bounds.Min.X, Chart.Bounds.Max.Y));
		DrawRect(FLinearColor::White, A.X, A.Y, B.X - A.X, B.Y - A.Y);
	}
	TArray<FCanvasUVTri> Tris;
	Tris.Reserve(Chart.TriangleClass.Num());
	for (int32 Block = 0; Block < Chart.TriangleBounds.Num(); ++Block)
	{
		if (!Visible(Chart.TriangleBounds[Block])) continue;
		const int32 End = FMath::Min((Block + 1) * FChartData::TrianglesPerBlock, Chart.TriangleClass.Num());
		for (int32 I = Block * FChartData::TrianglesPerBlock; I < End; ++I)
		{
			FCanvasUVTri Tri;
			Tri.V0_Pos = ToScreen(Chart.Triangles[3 * I]);
			Tri.V1_Pos = ToScreen(Chart.Triangles[3 * I + 1]);
			Tri.V2_Pos = ToScreen(Chart.Triangles[3 * I + 2]);
			Tri.V0_Color = Tri.V1_Color = Tri.V2_Color = SailingChart::AreaColour(Chart.TriangleClass[I]);
			Tris.Add(Tri);
		}
	}
	if (Tris.Num() > 0)
	{
		FCanvasTriangleItem Item(Tris, GWhiteTexture);
		Item.BlendMode = SE_BLEND_Opaque;
		Canvas->DrawItem(Item);
	}

	auto DrawPolyline = [&](const FChartData::FLine& L, const FLinearColor& Colour, float Thickness, bool bDashed = false)
	{
		if (!Visible(L.Bounds)) return;
		FVector2D Prev = ToScreen(L.Points[0]);
		for (int32 I = 1; I < L.Points.Num(); ++I)
		{
			const FVector2D P = ToScreen(L.Points[I]);
			if (!bDashed || (I % 2) == 1) DrawLine(Prev.X, Prev.Y, P.X, P.Y, Colour, Thickness);
			Prev = P;
		}
	};
	const double Zoom = Boat.GetChartMetersPerPixel(); // m per (1080p) pixel: smaller is closer in
	if (Zoom < 25.0) for (const FChartData::FLine& L : Chart.Contours) DrawPolyline(L, ContourInk, 1.f);
	for (const FChartData::FLine& L : Chart.Channels) DrawPolyline(L, Magenta, 1.f, true);
	for (const FChartData::FLine& L : Chart.Coast) DrawPolyline(L, Ink, 1.5f);
	if (Zoom < 8.0) for (const FChartData::FLine& L : Chart.Docks) DrawPolyline(L, Ink, 1.f);
	for (const FChartData::FLine& L : Chart.Bridges) DrawPolyline(L, Ink, 2.5f);

	UFont* Small = GEngine->GetSmallFont();
	UFont* Tiny = GEngine->GetTinyFont();
	// Soundings in feet, thinned so they never pile up.
	if (Zoom < 14.0)
	{
		TSet<int64> Used;
		const float Cell = 34.f * UIScale;
		for (const FVector3d& S : Chart.Soundings)
		{
			const FVector2D P = ToScreen(FVector2D(S.X, S.Y));
			if (P.X < 0 || P.Y < 0 || P.X > SW || P.Y > SH) continue;
			const int64 Key = (int64(P.X / Cell) << 32) | int64(P.Y / Cell);
			if (Used.Contains(Key)) continue;
			Used.Add(Key);
			DrawText(SailingChart::SoundingText(S.Z), Ink, P.X - 5.f * UIScale, P.Y - 6.f * UIScale, Tiny, UIScale);
		}
	}

	// Aids to navigation (U.S. Chart No. 1): buoys and beacons in their colors, a magenta flare on every light.
	TArray<FCanvasUVTri> Symbols;
	auto Tri = [&](const FVector2D& A, const FVector2D& B, const FVector2D& C, const FLinearColor& Colour)
	{
		FCanvasUVTri T;
		T.V0_Pos = A; T.V1_Pos = B; T.V2_Pos = C;
		T.V0_Color = T.V1_Color = T.V2_Color = Colour;
		Symbols.Add(T);
	};
	auto Quad = [&](const FVector2D& A, const FVector2D& B, const FVector2D& C, const FVector2D& D, const FLinearColor& Colour) { Tri(A, B, C, Colour); Tri(A, C, D, Colour); };
	const float U = FMath::Clamp(float(6.0 / FMath::Sqrt(Zoom)), 0.8f, 2.0f) * UIScale; // symbol size
	TArray<TPair<FVector2D, FString>> Labels;
	TArray<FVector2D> Outlines;
	for (const FNavaid& N : Lake.Navaids)
	{
		const FVector2D P = ToScreen(FVector2D(N.X, N.Y));
		if (P.X < -20 || P.Y < -20 || P.X > SW + 20 || P.Y > SH + 20) continue;
		const FLinearColor C = SailingChart::AidColour(N);
		const SailingChart::ESymbol Sym = SailingChart::SymbolFor(N);
		if (N.bLit)
		{
			// The light flare: a magenta teardrop from the position, pointing up and to the right.
			Tri(P, P + FVector2D(5.f, -12.f) * U, P + FVector2D(9.f, -9.f) * U, Magenta);
		}
		switch (Sym)
		{
		case SailingChart::ESymbol::Can:
			Quad(P + FVector2D(-3.f, -1.f) * U, P + FVector2D(3.f, -1.f) * U, P + FVector2D(4.f, -7.f) * U, P + FVector2D(-2.f, -7.f) * U, C);
			break;
		case SailingChart::ESymbol::Nun:
			Tri(P + FVector2D(-4.f, -1.f) * U, P + FVector2D(4.f, -1.f) * U, P + FVector2D(1.5f, -9.f) * U, C);
			break;
		case SailingChart::ESymbol::Beacon:
			if (N.Colours.Num() == 0 && N.DaymarkColours.Num() == 0 && N.CatLam == 0)
			{
				// A private or special-purpose beacon with no charted color: the plain beacon outline.
				Outlines.Add(P + FVector2D(0.f, -4.f) * U);
				break;
			}
			// Daybeacon: green square, red triangle (by the daymark's shape when charted, else by side).
			if (C.R > C.G) Tri(P + FVector2D(-4.f, -2.f) * U, P + FVector2D(4.f, -2.f) * U, P + FVector2D(0.f, -9.f) * U, C);
			else Quad(P + FVector2D(-3.5f, -2.f) * U, P + FVector2D(3.5f, -2.f) * U, P + FVector2D(3.5f, -9.f) * U, P + FVector2D(-3.5f, -9.f) * U, C);
			break;
		case SailingChart::ESymbol::LightMajor:
			Tri(P + FVector2D(-2.f, 0.f) * U, P + FVector2D(2.f, 0.f) * U, P + FVector2D(0.f, -14.f) * U, Magenta);
			break;
		default: // pillar, spar, sphere: a slanted buoy
			Quad(P + FVector2D(-3.5f, -1.f) * U, P + FVector2D(3.5f, -1.f) * U, P + FVector2D(4.5f, -8.f) * U, P + FVector2D(-1.f, -10.f) * U, C);
			break;
		}
		if (Zoom < 6.0) Labels.Add({ P + FVector2D(8.f, -2.f) * U, SailingChart::AidLabel(N) });
	}
	if (Symbols.Num() > 0)
	{
		FCanvasTriangleItem Item(Symbols, GWhiteTexture);
		Canvas->DrawItem(Item);
	}
	for (const FNavaid& N : Lake.Navaids)
	{
		// The position circle at the foot of each symbol.
		const FVector2D P = ToScreen(FVector2D(N.X, N.Y));
		if (P.X < 0 || P.Y < 0 || P.X > SW || P.Y > SH) continue;
		DrawRect(Ink, P.X - 1.5f, P.Y - 1.5f, 3.f, 3.f);
	}
	for (const FVector2D& O : Outlines)
	{
		const float H = 3.f * U;
		DrawLine(O.X - H, O.Y - H, O.X + H, O.Y - H, Ink, 1.f);
		DrawLine(O.X + H, O.Y - H, O.X + H, O.Y + H, Ink, 1.f);
		DrawLine(O.X + H, O.Y + H, O.X - H, O.Y + H, Ink, 1.f);
		DrawLine(O.X - H, O.Y + H, O.X - H, O.Y - H, Ink, 1.f);
	}
	for (const TPair<FVector2D, FString>& L : Labels) DrawText(L.Value, FLinearColor(0.3f, 0.05f, 0.3f), L.Key.X, L.Key.Y, Tiny, UIScale);
	if (Zoom < 10.0)
	{
		for (const FLandmark& L : Lake.Landmarks)
		{
			if (!L.bConspicuous || L.Name.IsEmpty() || L.Name == TEXT("Landmark")) continue;
			const FVector2D P = ToScreen(FVector2D(L.X, L.Y));
			if (P.X < 0 || P.Y < 0 || P.X > SW || P.Y > SH) continue;
			for (int32 I = 0; I < 12; ++I)
			{
				const float A0 = I * PI / 6.f, A1 = (I + 1) * PI / 6.f;
				DrawLine(P.X + 4.f * UIScale * FMath::Cos(A0), P.Y + 4.f * UIScale * FMath::Sin(A0), P.X + 4.f * UIScale * FMath::Cos(A1), P.Y + 4.f * UIScale * FMath::Sin(A1), Ink, 1.f);
			}
			DrawText(L.Name.ToUpper(), Ink, P.X + 6.f * UIScale, P.Y - 4.f * UIScale, Tiny, UIScale);
		}
	}

	// The plot: bearing lines (LOPs), the fix, the DR track.
	auto Circle = [&](const FVector2D& P, float R, const FLinearColor& Colour, float Thick)
	{
		for (int32 I = 0; I < 20; ++I)
		{
			const float A0 = I * PI / 10.f, A1 = (I + 1) * PI / 10.f;
			DrawLine(P.X + R * FMath::Cos(A0), P.Y + R * FMath::Sin(A0), P.X + R * FMath::Cos(A1), P.Y + R * FMath::Sin(A1), Colour, Thick);
		}
	};
	const double Now = Boat.GetSessionTime();
	for (const SailingNav::FBearing& B : Plot.Bearings)
	{
		const bool bRecent = Now - B.Time <= SailingNav::FPlot::FixWindow;
		const double Back = FMath::DegreesToRadians(SailingNav::MagneticToTrue(B.MagneticDeg, Var) + 180.0);
		// Drawn from the object to a little past the boat's side, as on paper.
		const double Length = FVector2D::Distance(B.Object, Plot.bHasFix ? Plot.Fix : Plot.Dr) * 1.12 + 300.0;
		const FVector2D A = ToScreen(B.Object), E = ToScreen(B.Object + FVector2D(FMath::Cos(Back), FMath::Sin(Back)) * Length);
		DrawLine(A.X, A.Y, E.X, E.Y, bRecent ? Ink : FLinearColor(0.4f, 0.4f, 0.4f), bRecent ? 1.5f : 1.f);
		const FVector2D Mid = A + (E - A) * 0.35;
		DrawText(FString::Printf(TEXT("%03.0f M"), B.MagneticDeg), Ink, Mid.X + 4.f, Mid.Y, Small, UIScale * 0.9f);
	}
	if (Plot.DrTrack.Num() > 0)
	{
		FVector2D Prev = ToScreen(Plot.DrTrack[0]);
		for (int32 I = 1; I <= Plot.DrTrack.Num(); ++I)
		{
			const FVector2D P = ToScreen(I < Plot.DrTrack.Num() ? Plot.DrTrack[I] : Plot.Dr);
			DrawLine(Prev.X, Prev.Y, P.X, P.Y, Ink, 1.f);
			Prev = P;
		}
		// DR position: a half circle (Chapman's convention) with "DR".
		const FVector2D D = ToScreen(Plot.Dr);
		for (int32 I = 0; I < 10; ++I)
		{
			const float A0 = PI + I * PI / 10.f, A1 = PI + (I + 1) * PI / 10.f;
			DrawLine(D.X + 7.f * UIScale * FMath::Cos(A0), D.Y + 7.f * UIScale * FMath::Sin(A0), D.X + 7.f * UIScale * FMath::Cos(A1), D.Y + 7.f * UIScale * FMath::Sin(A1), Ink, 2.f);
		}
		DrawLine(D.X - 7.f * UIScale, D.Y, D.X + 7.f * UIScale, D.Y, Ink, 2.f);
		DrawText(TEXT("DR"), Ink, D.X + 8.f * UIScale, D.Y - 18.f * UIScale, Small, UIScale);
	}
	if (Plot.bHasFix)
	{
		const FVector2D F = ToScreen(Plot.Fix);
		Circle(F, 7.f * UIScale, Ink, 2.f);
		DrawRect(Ink, F.X - 1.5f, F.Y - 1.5f, 3.f, 3.f);
		const int32 Minutes = FMath::RoundToInt((Now - Plot.FixTime) / 60.0);
		DrawText(FString::Printf(TEXT("FIX (%d min ago, cocked hat %.0f m)"), Minutes, Plot.FixSpread), Ink, F.X + 9.f * UIScale, F.Y + 4.f * UIScale, Small, UIScale * 0.9f);
	}

	// Other vessels as a chartplotter shows AIS targets (with the GPS on): a pointed outline along her heading.
	if (Boat.IsGpsShown())
	{
		if (const ATrafficManager* TM = ATrafficManager::Find(GetWorld()))
		{
			for (const FTrafficVessel& V : TM->GetSim().GetVessels())
			{
				const FVesselSnapshot S = V.Snapshot();
				const FVector2D P = ToScreen(FVector2D(S.X, S.Y));
				if (P.X < 0 || P.Y < 0 || P.X > SW || P.Y > SH) continue;
				const FLinearColor C = V.IsSail() ? FLinearColor(0.1f, 0.5f, 0.2f) : (V.Kind == ETrafficKind::Ship || V.Kind == ETrafficKind::TugAndTow ? Magenta : Ink);
				const double H = S.Heading;
				const FVector2D Fwd(FMath::Sin(H), -FMath::Cos(H)), Side(-Fwd.Y, Fwd.X);
				const float L = FMath::Max(7.f * UIScale, float(0.5 * S.Length / Mpp));
				DrawLine(P.X + Fwd.X * L, P.Y + Fwd.Y * L, P.X - Fwd.X * L + Side.X * L * 0.45f, P.Y - Fwd.Y * L + Side.Y * L * 0.45f, C, 1.5f);
				DrawLine(P.X + Fwd.X * L, P.Y + Fwd.Y * L, P.X - Fwd.X * L - Side.X * L * 0.45f, P.Y - Fwd.Y * L - Side.Y * L * 0.45f, C, 1.5f);
				DrawLine(P.X - Fwd.X * L + Side.X * L * 0.45f, P.Y - Fwd.Y * L + Side.Y * L * 0.45f, P.X - Fwd.X * L - Side.X * L * 0.45f, P.Y - Fwd.Y * L - Side.Y * L * 0.45f, C, 1.5f);
				// Course over ground vector: six minutes ahead.
				const FVector2D Ahead = ToScreen(FVector2D(S.X + S.VX * 360.0, S.Y + S.VY * 360.0));
				DrawLine(P.X, P.Y, Ahead.X, Ahead.Y, C, 1.f);
				if (Zoom < 12.0) DrawText(UTF8_TO_TCHAR(V.Name.c_str()), C, P.X + 8.f * UIScale, P.Y + 4.f * UIScale, Tiny, UIScale);
			}
		}
	}

	// The boat (GPS) and her heading.
	const FVector2D Me = Boat.GetMapPosition();
	const double HeadingT = Boat.GetHeadingTrueDeg();
	if (Boat.IsGpsShown())
	{
		const FVector2D P = ToScreen(Me);
		const double H = FMath::DegreesToRadians(HeadingT);
		const FVector2D Fwd(FMath::Sin(H), -FMath::Cos(H)), Side(-Fwd.Y, Fwd.X);
		const float L = 10.f * UIScale;
		DrawLine(P.X + Fwd.X * L, P.Y + Fwd.Y * L, P.X - Fwd.X * L + Side.X * L * 0.5f, P.Y - Fwd.Y * L + Side.Y * L * 0.5f, Bad, 2.5f);
		DrawLine(P.X + Fwd.X * L, P.Y + Fwd.Y * L, P.X - Fwd.X * L - Side.X * L * 0.5f, P.Y - Fwd.Y * L - Side.Y * L * 0.5f, Bad, 2.5f);
		DrawLine(P.X - Fwd.X * L + Side.X * L * 0.5f, P.Y - Fwd.Y * L + Side.Y * L * 0.5f, P.X - Fwd.X * L - Side.X * L * 0.5f, P.Y - Fwd.Y * L - Side.Y * L * 0.5f, Bad, 2.5f);
		DrawLine(P.X, P.Y, P.X + Fwd.X * 60.f * UIScale, P.Y + Fwd.Y * 60.f * UIScale, Bad, 1.f);
	}

	// Course line: from the boat (GPS) or the DR to the crosshair, with its true and magnetic course and distance.
	const FVector2D From = Boat.IsGpsShown() ? Me : Plot.Dr;
	const FVector2D FS = ToScreen(From), CS(SW * 0.5f, SH * 0.5f);
	DrawLine(CS.X - 12.f, CS.Y, CS.X + 12.f, CS.Y, Ink, 1.f);
	DrawLine(CS.X, CS.Y - 12.f, CS.X, CS.Y + 12.f, Ink, 1.f);
	const double Dist = FVector2D::Distance(From, Center);
	if (Dist > 20.0)
	{
		DrawLine(FS.X, FS.Y, CS.X, CS.Y, Magenta, 1.5f);
		const double Course = SailingNav::BearingDeg(From, Center);
		const double Sog = FMath::Max(Boat.GetBoatModel().GetTelemetry().SpeedThroughWater, 0.3);
		DrawText(FString::Printf(TEXT("%03.0f T  %03.0f M  %s  %.0f min"), Course, SailingNav::TrueToMagnetic(Course, Var), *SailingNav::FormatDistance(Dist), Dist / Sog / 60.0),
			Magenta, CS.X + 14.f * UIScale, CS.Y + 6.f * UIScale, Small, UIScale);
	}

	// Compass rose: true outside (star at north), magnetic inside, turned by the variation.
	const FVector2D Rose(SW - 150.f * UIScale, SH - 170.f * UIScale);
	const float RO = 110.f * UIScale, RI = 80.f * UIScale;
	Circle(Rose, RO, Magenta, 1.f);
	Circle(Rose, RI, Magenta, 1.f);
	for (int32 D = 0; D < 360; D += 10)
	{
		const float AT = FMath::DegreesToRadians(float(D)), AM = FMath::DegreesToRadians(float(D + Var));
		const float LT = D % 30 == 0 ? 10.f : 5.f;
		DrawLine(Rose.X + RO * FMath::Sin(AT), Rose.Y - RO * FMath::Cos(AT), Rose.X + (RO - LT * UIScale) * FMath::Sin(AT), Rose.Y - (RO - LT * UIScale) * FMath::Cos(AT), Magenta, 1.f);
		DrawLine(Rose.X + RI * FMath::Sin(AM), Rose.Y - RI * FMath::Cos(AM), Rose.X + (RI - LT * UIScale) * FMath::Sin(AM), Rose.Y - (RI - LT * UIScale) * FMath::Cos(AM), Magenta, 1.f);
		if (D % 30 == 0)
		{
			DrawText(FString::Printf(TEXT("%d"), D), Magenta, Rose.X + (RO + 12.f * UIScale) * FMath::Sin(AT) - 8.f * UIScale, Rose.Y - (RO + 12.f * UIScale) * FMath::Cos(AT) - 6.f * UIScale, Tiny, UIScale);
		}
	}
	Symbols.Reset();
	Tri(Rose + FVector2D(0.f, -RO - 4.f * UIScale), Rose + FVector2D(-5.f * UIScale, -RO + 10.f * UIScale), Rose + FVector2D(5.f * UIScale, -RO + 10.f * UIScale), Magenta);
	{
		FCanvasTriangleItem Star(Symbols, GWhiteTexture);
		Canvas->DrawItem(Star);
	}
	const double VarMin = FMath::Abs(Var) * 60.0;
	DrawText(FString::Printf(TEXT("VAR %d%c%02d'%s (%d)"), int32(VarMin / 60.0), TCHAR(0xB0), int32(FMath::Fmod(VarMin, 60.0)), Var >= 0.0 ? TEXT("E") : TEXT("W"), 2026), Magenta, Rose.X - 50.f * UIScale, Rose.Y - 6.f * UIScale, Small, UIScale);

	// Scale bar: one nautical mile (or a tenth).
	const double BarM = Zoom > 3.0 ? SailingNav::MetersPerNauticalMile : 0.1 * SailingNav::MetersPerNauticalMile;
	const float BarPx = float(BarM / Mpp), BX = 30.f * UIScale, BY = SH - 40.f * UIScale;
	DrawRect(Ink, BX, BY, BarPx, 4.f * UIScale);
	DrawText(Zoom > 3.0 ? TEXT("1 nautical mile") : TEXT("0.1 nautical mile"), Ink, BX, BY - 18.f * UIScale, Small, UIScale);

	// Title block and keys.
	DrawRect(FLinearColor(1.f, 1.f, 1.f, 0.85f), 10.f * UIScale, 10.f * UIScale, 520.f * UIScale, 92.f * UIScale);
	Text(FString::Printf(TEXT("%s  (NOAA ENC)  soundings in feet at MLLW"), *Lake.LakeName), 20.f, 16.f, Ink, 0.95f);
	FTideEvent Next;
	const bool bNext = GM->GetNextTide(Next);
	const int32 NextMin = bNext ? int32(FMath::Fmod((Next.Time + GM->GetUtcOffsetHours() * 3600.0) / 60.0, 1440.0)) : 0;
	Text(FString::Printf(TEXT("Tide %+.1f ft%s   Not for navigation"), GM->GetTideHeight() / 0.3048,
		bNext ? *FString::Printf(TEXT(", %s %02d:%02d"), Next.Type == FTideEvent::High ? TEXT("high") : TEXT("low"), NextMin / 60, NextMin % 60) : TEXT("")), 20.f, 40.f, Ink, 0.85f);
	Text(TEXT("Mouse pans, wheel zooms, P closes.  U bearing on what the camera faces,  O GPS,  I clear the plot"), 20.f, 64.f, Ink, 0.7f);
}

void ASailingHUD::DrawInstruments(const ASailboatPawn& Boat)
{
	using namespace SailingHUDLocal;
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
	using namespace SailingHUDLocal;
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
	using namespace SailingHUDLocal;
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	if (!GM) return;
	const FWeatherState& W = GM->GetWeatherState();
	const FBoatTelemetry& T = Boat.GetBoatModel().GetTelemetry();
	const float X = Canvas->ClipX / UIScale - 300.f, Y = Canvas->ClipY / UIScale - 112.f;
	DrawRect(Panel, X * UIScale, Y * UIScale, 290.f * UIScale, 100.f * UIScale);
	const int32 Hour = int32(W.HourOfDay), Minute = int32(FMath::Fmod(W.HourOfDay, 1.0) * 60.0);
	Text(FString::Printf(TEXT("%hs  %02d:%02d"), WeatherPresetName(GM->GetWeather().GetPreset()), Hour, Minute), X + 10.f, Y + 8.f, FLinearColor::White, 0.9f);
	Text(FString::Printf(TEXT("Wind %.0f kn  waves %.2f m"), T.TrueWindSpeed / kKnot, GM->GetWaves().SignificantHeightAt(Boat.GetBoatModel().OriginPosition().X, Boat.GetBoatModel().OriginPosition().Y)), X + 10.f, Y + 32.f, Dim, 0.85f);
	Text(FString::Printf(TEXT("Visibility %.0f km%s"), W.VisibilityKm, W.Rain > 0.05 ? TEXT("  rain") : TEXT("")), X + 10.f, Y + 54.f, Dim, 0.85f);
	if (W.Storm != EStormPhase::None)
	{
		Text(FString(StormPhaseName(W.Storm)), X + 10.f, Y + 76.f, W.Storm == EStormPhase::GustFront || W.Storm == EStormPhase::Rain ? Bad : Warn, 0.9f);
	}
}

void ASailingHUD::DrawDrillAndStatus(const ASailboatPawn& Boat)
{
	using namespace SailingHUDLocal;
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
	using namespace SailingHUDLocal;
	const TArray<TPair<FString, FString>> Rows = Boat.GetMenuRows();
	// Sections: what you sail and against whom, the water and weather, how the game helps, display and keys.
	const TMap<int32, const TCHAR*> Sections = { { 0, TEXT("SAILING") }, { 6, TEXT("WATER AND WEATHER") }, { 11, TEXT("HELP AND CONTROLS") }, { 15, TEXT("DISPLAY, SOUND AND KEYS") } };
	const float RowH = 29.f, SectionH = 24.f;
	const float W = 760.f, H = 110.f + Rows.Num() * RowH + Sections.Num() * SectionH;
	const float X = Canvas->ClipX / UIScale * 0.5f - W * 0.5f, Y = FMath::Max(10.f, Canvas->ClipY / UIScale * 0.5f - H * 0.5f);
	DrawRect(FLinearColor(0.f, 0.f, 0.f, 0.72f), X * UIScale, Y * UIScale, W * UIScale, H * UIScale);
	Text(TEXT("Settings"), X + 20.f, Y + 12.f, FLinearColor::White, 1.1f, true);
	float RY = Y + 50.f;
	for (int32 I = 0; I < Rows.Num(); ++I)
	{
		if (const TCHAR* const* Section = Sections.Find(I))
		{
			Text(*Section, X + 20.f, RY + 4.f, FLinearColor(0.55f, 0.75f, 1.f), 0.68f);
			RY += SectionH;
		}
		const bool bSel = I == Boat.GetMenuIndex();
		ON_SCOPE_EXIT { RY += RowH; };
		if (bSel) DrawRect(FLinearColor(0.3f, 0.5f, 0.8f, 0.5f), (X + 10.f) * UIScale, (RY - 4.f) * UIScale, (W - 20.f) * UIScale, (RowH - 1.f) * UIScale);
		Text(Rows[I].Key, X + 24.f, RY, bSel ? FLinearColor::White : Dim, 0.9f);
		Text(FString::Printf(TEXT("<  %s  >"), *Rows[I].Value), X + 290.f, RY, bSel ? Good : FLinearColor::White, 0.9f);
	}
	Text(TEXT("Up/Down choose, Left/Right change, Tab (Menu) closes"), X + 20.f, Y + H - 54.f, Dim, 0.8f);
	// Required attribution for the map data (OpenStreetMap is ODbL); see CREDITS.md.
	Text(TEXT("Map data (c) OpenStreetMap contributors, ODbL. Terrain: USGS 3DEP."), X + 20.f, Y + H - 30.f, Dim, 0.7f);
	const ASailingGameMode* GM = GetWorld()->GetAuthGameMode<ASailingGameMode>();
	Text(GM && GM->GetLake().IsTidal() ? TEXT("Chart, tides and currents: NOAA (ENC, CO-OPS). Not for navigation.")
		: TEXT("Lake depths and levels: Texas Water Development Board."), X + 20.f, Y + H - 12.f, Dim, 0.7f);
}

void ASailingHUD::DrawControlsCard(const ASailboatPawn& Boat)
{
	using namespace SailingHUDLocal;
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
		{ TEXT("Chart, bearing, GPS, clear the plot (coast)"), TEXT("P, U, O, I") },
		{ TEXT("Ship's log"), TEXT("Y") },
		{ TEXT("Watch your last run (ghost: Tab > Ghost)"), TEXT(",") },
		{ TEXT("Photo mode, take a photo"), TEXT("9, Enter") },
		{ TEXT("Learning mode"), TEXT("L            Y button") },
		{ TEXT("Difficulty"), TEXT("K") },
		{ TEXT("Settings (area, races, traffic, weather, keys)"), TEXT("Tab          Menu") },
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
	using namespace SailingHUDLocal;
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

FString SailingPointOfSail(double TwaDeg, bool bInIrons) { return SailingHUDLocal::PointOfSail(TwaDeg, bInIrons); }

/** Graphics G4: the coach's trim and safety tips, shared by the canvas HUD and the Slate HUD (severity 0 note, 1 good, 2 caution, 3 fault). */
void SailingCollectTips(const ASailboatPawn& Boat, const UWorld* World, TArray<TPair<FString, int32>>& Tips)
{
	using namespace SailingHUDLocal;
	const FBoatModel& Model = Boat.GetBoatModel();
	const FBoatTelemetry& T = Model.GetTelemetry();
	const FBoatControls& C = Boat.GetControls();
	const double TwaDeg = FMath::RadiansToDegrees(T.TrueWindAngle);
	const double HeelLeeward = FMath::RadiansToDegrees(T.Heel) * Model.GetState().WindwardSide;

	const FString Pos = PointOfSail(TwaDeg, T.bInIrons);
	Tips.Add({ FString::Printf(TEXT("%s  (%s tack)"), *Pos, TwaDeg >= 0.0 ? TEXT("starboard") : TEXT("port")), 0 });

	if (T.bInIrons)
	{
		Tips.Add({ TEXT("Stuck head to wind. Push the tiller toward the boom and hold the jib out to the side the bow should go (backing it)."), 2 });
		Tips.Add({ TEXT("You will drift backward first; the bow falls off, then trim in and sail away."), 0 });
	}
	else if (FMath::Abs(TwaDeg) < 35.0)
	{
		Tips.Add({ TEXT("Too close to the wind: the sails cannot draw. Bear away (steer away from the wind) to about 45 degrees."), 2 });
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
			Tips.Add({ bUpwind ? TEXT("Jib is luffing (windward telltales lifting): trim the jib in (E), or bear away a little.") : TEXT("Jib is luffing: trim the jib in (E) until the luff stops bubbling."), 2 });
		else if (JibStall >= 2)
			Tips.Add({ TEXT("Jib is stalled (leeward telltales drooping): ease the jib (Q), or head up a little."), 2 });
		else
			Tips.Add({ TEXT("Jib telltales streaming: well trimmed."), 1 });

		if (MainLuff >= 2)
			Tips.Add({ TEXT("Main is luffing: trim the mainsheet in (W)."), 2 });
		else if (MainStall >= 2)
			Tips.Add({ TEXT("Main is stalled (leech telltales curling behind the sail): ease the mainsheet (S)."), 2 });
		else
			Tips.Add({ TEXT("Main leech telltales streaming: well trimmed."), 1 });
	}

	if (HeelLeeward > 22.0)
		Tips.Add({ USailingSettings::Get()->UseSimpleControls() ? TEXT("Heeling too much: hike out (F) and ease the main (S) in the puffs.")
			: TEXT("Heeling too much: hike out (F), ease the main or drop the traveler (C), flatten with backstay (8)."), 3 });
	else if (HeelLeeward > 12.0 && C.Hike < 0.8)
		Tips.Add({ TEXT("Building breeze: get the crew hiking (F)."), 0 });
	if (T.HelmForce > 40.0)
		Tips.Add({ TEXT("Heavy weather helm: the boat wants to round up. Ease the main to balance her."), 2 });
	if (const ASailingGameMode* GM = World ? World->GetAuthGameMode<ASailingGameMode>() : nullptr)
	{
		const FWeatherState& W = GM->GetWeatherState();
		if (W.Storm == EStormPhase::Building)
			Tips.Add({ TEXT("Thunderstorm building to the west-northwest: watch for the dark line of the gust front on the water and reef or head in."), 3 });
		else if (W.Storm == EStormPhase::GustFront || W.Storm == EStormPhase::Rain)
			Tips.Add({ TEXT("Storm: depower (ease sheets, hike), keep the bow off the wind, and stay clear of the mast in lightning."), 3 });
	}
	if (FMath::Abs(TwaDeg) > 160.0 && !C.bWingOnWing)
		Tips.Add({ TEXT("Dead downwind: try wing-on-wing (G), jib out on the opposite side. Watch for an accidental gybe."), 0 });
	if (FMath::Abs(TwaDeg) > 170.0)
		Tips.Add({ TEXT("Sailing by the lee risks an accidental gybe: steer a few degrees toward the wind."), 2 });

}

void ASailingHUD::DrawTips(const ASailboatPawn& Boat)
{
	using namespace SailingHUDLocal;
	TArray<TPair<FString, int32>> Collected;
	SailingCollectTips(Boat, GetWorld(), Collected);
	TArray<TPair<FString, FLinearColor>> Tips;
	for (const TPair<FString, int32>& T : Collected) Tips.Add({ T.Key, T.Value == 1 ? Good : (T.Value == 2 ? Warn : (T.Value == 3 ? Bad : FLinearColor::White)) });
	const float X = Canvas->ClipX / UIScale * 0.5f - 330.f;
	float Y = 18.f;
	DrawRect(Panel, X * UIScale, 10.f * UIScale, 660.f * UIScale, (Tips.Num() * 24.f + 16.f) * UIScale);
	for (const TPair<FString, FLinearColor>& Tip : Tips)
	{
		Text(Tip.Key, X + 12.f, Y, Tip.Value, 0.85f);
		Y += 24.f;
	}
}
