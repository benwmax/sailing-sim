#include "ShipHandling.h"

#include <algorithm>
#include <cmath>

namespace Sailing
{
	namespace
	{
		// Making sternway the rudder works the other way and the helm is shifted (FAutopilot's rule: from 0.3 m/s astern,
		// fully reversed by 0.8), so a ship falling back head to wind still pays off onto the side she was turning to.
		double AsternSense(const FBoatTelemetry& T) { return Clamp(1.0 + 4.0 * std::min(T.ForwardSpeed + 0.3, 0.0), -1.0, 1.0); }
	}

	const char* FShipHandling::StepName(EShipManoeuvreStep Step)
	{
		switch (Step)
		{
		case EShipManoeuvreStep::Idle: return "";
		case EShipManoeuvreStep::HelmsALee: return "Helm's a-lee";
		case EShipManoeuvreStep::MainsailHaul: return "Mainsail haul";
		case EShipManoeuvreStep::LetGoAndHaul: return "Let go and haul";
		case EShipManoeuvreStep::BearAway: return "Up helm, square the yards";
		case EShipManoeuvreStep::Gybing: return "Stern through the wind";
		case EShipManoeuvreStep::HaulUp: return "Brace up, haul her to the wind";
		case EShipManoeuvreStep::HoveTo: return "Hove to";
		case EShipManoeuvreStep::Done: return "Done";
		case EShipManoeuvreStep::MissedStays: return "Missed stays: wear ship";
		}
		return "";
	}

	void FShipHandling::Start(EShipManoeuvre Manoeuvre, const FBoatModel& Boat)
	{
		const FBoatTelemetry& T = Boat.GetTelemetry();
		Current = Manoeuvre;
		Time = StepTime = 0.0;
		FromSide = T.TrueWindAngle >= 0.0 ? 1.0 : -1.0;
		Helm = Boat.GetState().RudderAngle / std::max(Boat.GetConfig().MaxRudderAngleDeg * kDegToRad, 1e-3);
		Ordered = std::fabs(T.TrueWindAngle) * kRadToDeg;
		for (int M = 0; M < kMaxMasts; ++M) HeldBrace[M] = FromSide;
		bCoursesRisen = false;
		bWayOn = false;
		Pilot.MaxTiller = Settings.PilotMaxTiller;
		Pilot.bKeepShortOfStall = Settings.PilotMaxTiller <= 0.6;
		SpeedBefore = std::max(T.ForwardSpeed, 0.5);
		switch (Manoeuvre)
		{
		case EShipManoeuvre::None: StepNow = EShipManoeuvreStep::Idle; break;
		case EShipManoeuvre::Tack: StepNow = EShipManoeuvreStep::HelmsALee; break;
		case EShipManoeuvre::Wear: StepNow = EShipManoeuvreStep::BearAway; break;
		case EShipManoeuvre::HeaveTo: StepNow = EShipManoeuvreStep::HoveTo; break;
		}
	}

	void FShipHandling::LowerCourses(const FBoatConfig& C, FBoatControls& Controls)
	{
		if (!bCoursesRisen) return;
		bCoursesRisen = false;
		for (int I = 0; I < int(C.Square.Sails.size()) && I < kMaxSquareSails; ++I)
			if (C.Square.Sails[I].Kind == ESquareSailKind::Course) Controls.SquareSet[I] = HeldSet[I];
	}

	bool FShipHandling::MainDraws(const FBoatModel& Boat) const
	{
		// The main mast's lowest set sail full (a positive angle of attack on the new side's face).
		const FBoatConfig& C = Boat.GetConfig();
		const FBoatTelemetry& T = Boat.GetTelemetry();
		for (int I = 0; I < int(C.Square.Sails.size()) && I < T.NumSquareSails; ++I)
			if (C.Square.Sails[I].Mast == 1 && Boat.GetState().SquareOut[I] > 0.5)
				return T.SquareStrips[I].AlphaN > Settings.DrawAlphaDeg * kDegToRad;
		return true;
	}

	void FShipHandling::HelmToward(const FBoatModel& Boat, FBoatControls& Controls, double Target, double Dt)
	{
		// The wheel from amidships to hard over in WheelHardOverSeconds (a tiller: a second).
		const double HardOver = Boat.GetConfig().WheelHardOverSeconds > 0.0 ? Boat.GetConfig().WheelHardOverSeconds : 1.0;
		Helm = MoveToward(Helm, Clamp(Target, -1.0, 1.0), Dt / HardOver);
		Controls.Tiller = Helm;
	}

	void FShipHandling::SteerFor(const FBoatModel& Boat, FBoatControls& Controls, double TwaDeg, double Dt)
	{
		Pilot.TargetTWADeg = TwaDeg;
		HelmToward(Boat, Controls, Pilot.Update(Boat), Dt);
	}

	bool FShipHandling::Update(const FBoatModel& Boat, FBoatControls& Controls, double Dt)
	{
		if (!IsActive()) return false;
		const FBoatConfig& C = Boat.GetConfig();
		const FBoatTelemetry& T = Boat.GetTelemetry();
		const double S = FromSide;
		const double Twa = T.TrueWindAngle * kRadToDeg;
		const double Up = S * Twa; // the old side's angle: 67 close-hauled, 0 head to wind, negative past it
		Time += Dt;
		StepTime += Dt;
		auto Go = [this](EShipManoeuvreStep Next) { StepNow = Next; StepTime = 0.0; };
		const bool bSquare = C.HasSquareRig();

		if (Current == EShipManoeuvre::Tack)
		{
			if (StepNow == EShipManoeuvreStep::HelmsALee || StepNow == EShipManoeuvreStep::MainsailHaul)
			{
				// She hangs head to wind, or falls back on the old tack: missed stays. Wear ship.
				// Still short of the wind long after the helm went over, or fallen back on the old tack: missed stays. (Once
				// through the wind she is left to the fore yards aback, which pay her head off however slowly.)
				if (Time > Settings.MissedStaysSeconds && Up > 0.0)
				{
					// Wear ship.
					Current = EShipManoeuvre::Wear;
					Ordered = Up;
					Go(EShipManoeuvreStep::MissedStays);
					return Update(Boat, Controls, 0.0);
				}
				HelmToward(Boat, Controls, S * AsternSense(T), Dt); // hard a-lee: up into the wind (shifted with sternway)
				Controls.JibSheet = 1.0;                    // the headsheets let fly
				// "Rise tacks and sheets": nearing the wind the courses' clews are hauled up, so they do not hold her back.
				if (bSquare && Up < Settings.RiseTacksDeg && !bCoursesRisen)
				{
					bCoursesRisen = true;
					for (int I = 0; I < int(C.Square.Sails.size()) && I < kMaxSquareSails; ++I)
					{
						HeldSet[I] = Controls.SquareSet[I];
						if (C.Square.Sails[I].Kind == ESquareSailKind::Course && Controls.SquareSet[I] == ESailSet::Set) Controls.SquareSet[I] = ESailSet::Clewed;
					}
				}
				Controls.MainSheet = 0.0;                   // the spanker amidships, driving her stern round
				if (StepNow == EShipManoeuvreStep::HelmsALee)
				{
					for (int M = 0; M < kMaxMasts; ++M) Controls.Brace[M] = HeldBrace[M];
					if (Up < Settings.MainsailHaulDeg) Go(EShipManoeuvreStep::MainsailHaul);
				}
				else
				{
					// The main and mizzen yards round for the new tack; the fore yards held, their sails aback, paying her
					// head off. "Let go and haul" once she is past the wind and the main yards draw (their sails full).
					Controls.Brace[0] = HeldBrace[0];
					for (int M = 1; M < kMaxMasts; ++M) Controls.Brace[M] = -S * Settings.MainHaulBrace;
					if (Up < -Settings.LetGoDeg && (!bSquare || MainDraws(Boat) || Up < -Settings.LetGoLatestDeg)) Go(EShipManoeuvreStep::LetGoAndHaul);
				}
				return true;
			}
			if (StepNow == EShipManoeuvreStep::LetGoAndHaul)
			{
				// The fore yards round; the trimmer has the rest; the courses' tacks and sheets hauled down again; meet her
				// and steer for the new tack.
				// The fore yards swung round and braced up (the trimmer has them once she has way on).
				if (bSquare && !bWayOn) Controls.Brace[0] = -S;
				LowerCourses(C, Controls);
				// "Full for stays": a little free of close-hauled until she has way on again, then up to the wind.
				if (T.ForwardSpeed > Settings.WayOnShare * SpeedBefore) bWayOn = true;
				const double Course = Settings.CloseHauledDeg + (bWayOn ? 0.0 : Settings.FullDeg);
				// Paying her off, the spanker is brailed in (it would hold her stern down to leeward).
				Controls.bMainDown = !bWayOn && Settings.bBrailToPayOff;
				SteerFor(Boat, Controls, -S * Course, Dt);
				if ((bWayOn && Up < -(Settings.CloseHauledDeg - 8.0)) || StepTime > Settings.GatherWaySeconds)
				{
					Controls.bMainDown = false;
					Go(EShipManoeuvreStep::Done);
				}
				return true;
			}
			return false;
		}

		if (Current == EShipManoeuvre::Wear)
		{
			LowerCourses(C, Controls);
			const double End = 360.0 - Settings.CloseHauledDeg;
			// Where she is, as the course measured round from the old side (0 head to wind .. 360 head to wind again).
			const double Round = Up >= 0.0 || Ordered < 90.0 ? std::max(Up, 0.0) : 360.0 + Up;
			// The officer brings the ordered course round at his pace, but never more than WearLeadDeg ahead of her.
			Ordered = std::min({ Ordered + Settings.WearTurnDegPerSecond * Dt, End, Round + Settings.WearLeadDeg });
			// The course ordered as a signed true wind angle: on the old side up to 180, then on the new side.
			const double Target = Ordered <= 180.0 ? S * Ordered : -S * (360.0 - Ordered);
			if (StepNow == EShipManoeuvreStep::MissedStays && StepTime > 5.0) Go(EShipManoeuvreStep::BearAway);
			if (StepNow == EShipManoeuvreStep::BearAway && Round >= 160.0) Go(EShipManoeuvreStep::Gybing);
			if (StepNow == EShipManoeuvreStep::Gybing && Round >= 200.0) Go(EShipManoeuvreStep::HaulUp);
			// The spanker brailed up until she is round (it would hold her stern up to the wind).
			Controls.bMainDown = StepNow != EShipManoeuvreStep::HaulUp;
			SteerFor(Boat, Controls, Target, Dt);
			if (StepNow == EShipManoeuvreStep::HaulUp && Ordered >= End && std::fabs(Twa - Target) < 8.0) Go(EShipManoeuvreStep::Done);
			if (Time > Settings.WearGiveUpSeconds) Go(EShipManoeuvreStep::Done);
			return true;
		}

		if (Current == EShipManoeuvre::HeaveTo)
		{
			// The main yards square and aback, the fore and mizzen full and braced up.
			Controls.Brace[0] = S;
			Controls.Brace[1] = -S * Settings.HoveToBraceShare;
			if (bSquare && C.Square.NumMasts > 2) Controls.Brace[2] = S;
			Controls.JibSheet = 0.6;
			Controls.MainSheet = Settings.HoveToSpankerSheet;
			// The helm keeps her lying some points off the wind (she comes up to it with the main topsail aback, and the
			// fore topsail full pays her off again), at the pace a quartermaster would.
			SteerFor(Boat, Controls, S * Settings.HoveToTwaDeg, Dt);
			return true;
		}
		return false;
	}
}
