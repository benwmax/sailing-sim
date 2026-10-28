#include "Showroom.h"
#include "SailboatPawn.h"
#include "SailingGameMode.h"
#include "UI/SailFrontEnd.h"
#include "Kismet/GameplayStatics.h"

namespace SailShowroom
{
	EShowroomStage StageFor(ESailScreen Screen, bool bInGame)
	{
		if (bInGame) return Screen == ESailScreen::ConditionsInGame ? EShowroomStage::Weather : EShowroomStage::None;
		if (Screen == ESailScreen::Boat) return EShowroomStage::Boat;
		if (Screen == ESailScreen::Conditions) return EShowroomStage::Weather;
		return EShowroomStage::None;
	}

	bool SameConditions(const FSailConditions& A, const FSailConditions& B)
	{
		return A.WindFromDeg == B.WindFromDeg && A.WindKn == B.WindKn && A.GustKn == B.GustKn && A.Sky == B.Sky && A.LocalHour == B.LocalHour
			&& A.Month == B.Month && A.Day == B.Day && A.AirTempF == B.AirTempF && A.LakeLevelFt == B.LakeLevelFt && A.PresetId == B.PresetId
			&& A.RealDay == B.RealDay;
	}

	FVector2D FindOpenWater(TFunctionRef<double(double, double)> Height, double X, double Y, double MinDepthM, double ClearM)
	{
		auto Open = [&](double PX, double PY)
		{
			if (Height(PX, PY) > -MinDepthM) return false;
			// No ground above the water within ClearM (sixteen bearings, at the radius and half of it).
			for (int32 K = 0; K < 16; ++K)
			{
				const double A = K * (2.0 * UE_DOUBLE_PI / 16.0);
				for (const double R : { 0.5 * ClearM, ClearM })
				{
					if (Height(PX + R * FMath::Cos(A), PY + R * FMath::Sin(A)) > -0.5) return false;
				}
			}
			return true;
		};
		if (Open(X, Y)) return FVector2D(X, Y);
		for (double R = 25.0; R <= 1500.0; R += 25.0)
		{
			// Around each ring, nearest first; the first bearing found wins (east, then round toward north).
			const int32 N = FMath::Max(8, int32(2.0 * UE_DOUBLE_PI * R / 25.0));
			for (int32 K = 0; K < N; ++K)
			{
				const double A = K * (2.0 * UE_DOUBLE_PI / N);
				const double PX = X + R * FMath::Cos(A), PY = Y + R * FMath::Sin(A);
				if (Open(PX, PY)) return FVector2D(PX, PY);
			}
		}
		return FVector2D(X, Y);
	}
}

void FSailShowroom::Update(ASailboatPawn* Pawn, ASailingGameMode* GameMode, ESailScreen Screen, bool bInGame, int32 BoatToShow,
	const FSailConditions& Pending, double Now)
{
	const EShowroomStage Want = SailShowroom::StageFor(Screen, bInGame);
	if (Want != Stage || bInGame != bStageInGame) SetStage(Pawn, GameMode, Want, bInGame);
	// The boat: the one focused on the Boat screen, the chosen one elsewhere (the title shows the last session's boat, and
	// a boat chosen and backed out of stays). Not in game: the session's boat is the one sailing.
	if (!bInGame && Pawn && BoatToShow >= 0)
	{
		if (BoatToShow != WantBoat)
		{
			WantBoat = BoatToShow;
			BoatDebounce.DelaySeconds = 0.2;
			BoatDebounce.Changed(Now);
		}
		if (BoatDebounce.Fire(Now) && (Pawn->GetBoatTypeIndex() != WantBoat || Pawn->GetShowroomLoadingType() >= 0)) Pawn->ShowBoat(WantBoat);
	}
	// The conditions: right away on entering the screen, then each change once it has stood for 200 ms.
	if (Stage == EShowroomStage::Weather && GameMode)
	{
		if (!bHavePreviewed)
		{
			bHavePreviewed = true;
			Previewed = Pending;
			if (!bInGame) GameMode->PreviewConditions(Pending); // in game the world already shows the session's
		}
		else if (!SailShowroom::SameConditions(Pending, Previewed))
		{
			Previewed = Pending;
			ConditionsDebounce.DelaySeconds = 0.2;
			ConditionsDebounce.Changed(Now);
		}
		if (ConditionsDebounce.Fire(Now)) GameMode->PreviewConditions(Previewed);
	}
}

void FSailShowroom::SetStage(ASailboatPawn* Pawn, ASailingGameMode* GameMode, EShowroomStage NewStage, bool bInGame)
{
	if (Stage == EShowroomStage::Weather && GameMode)
	{
		// Leaving the preview: in the front end it is the choice (a change still waiting goes in first); in game Back puts
		// the session's back (Apply has already committed and ended it).
		if (!bStageInGame && ConditionsDebounce.IsPending()) GameMode->PreviewConditions(Previewed);
		GameMode->EndPreview(!bStageInGame);
		if (bStageInGame)
		{
			GameMode->SetPreviewLive(false);
			if (bUnpaused && GameMode->GetWorld()) UGameplayStatics::SetGamePaused(GameMode, true);
		}
	}
	ConditionsDebounce.Cancel();
	bHavePreviewed = false;
	bUnpaused = false;
	Stage = NewStage;
	bStageInGame = bInGame;
	if (Stage == EShowroomStage::Weather && bInGame && GameMode)
	{
		// Change conditions in game: the world runs while it is open (the pause menu had paused it).
		GameMode->SetPreviewLive(true);
		if (GameMode->GetWorld() && GameMode->GetWorld()->IsPaused())
		{
			UGameplayStatics::SetGamePaused(GameMode, false);
			bUnpaused = true;
		}
	}
	if (Pawn) Pawn->SetShowroomStage(Stage, !bInGame);
}

void FSailShowroom::End(ASailboatPawn* Pawn, ASailingGameMode* GameMode)
{
	// The menus are closing: the HUD sees to the pause (Resume unpauses), so the stage is left without pausing again.
	bUnpaused = false;
	// A world being torn down (the cast off's reload) has nothing to put back.
	const UWorld* World = Pawn ? Pawn->GetWorld() : GameMode ? GameMode->GetWorld() : nullptr;
	if (!World || World->bIsTearingDown || (Pawn && !IsValid(Pawn)) || (GameMode && !IsValid(GameMode))) { Stage = EShowroomStage::None; return; }
	if (Stage != EShowroomStage::None) SetStage(Pawn, GameMode, EShowroomStage::None, bStageInGame);
	WantBoat = -1;
	BoatDebounce.Cancel();
}
