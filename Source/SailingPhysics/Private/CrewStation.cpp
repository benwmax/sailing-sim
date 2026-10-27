#include "CrewStation.h"
#include "SailingMath.h"
#include <algorithm>
#include <cmath>

namespace Sailing
{
	const char* CrewStationName(ECrewStation S)
	{
		switch (S)
		{
		case ECrewStation::Helm: return "helm";
		case ECrewStation::JibTrimmer: return "jib-trimmer";
		case ECrewStation::MainTrimmer: return "main-trimmer";
		case ECrewStation::None:
		case ECrewStation::Count:
		default: return "";
		}
	}

	ECrewStation CrewStationFromName(const std::string& Name)
	{
		for (int I = 1; I < int(ECrewStation::Count); ++I) if (Name == CrewStationName(ECrewStation(I))) return ECrewStation(I);
		return ECrewStation::Count;
	}

	ECrewStation NextCrewStation(ECrewStation S)
	{
		switch (S)
		{
		case ECrewStation::Helm: return ECrewStation::JibTrimmer;
		case ECrewStation::JibTrimmer: return ECrewStation::MainTrimmer;
		case ECrewStation::MainTrimmer: return ECrewStation::Helm;
		case ECrewStation::None:
		case ECrewStation::Count:
		default: return S;
		}
	}

	const char* StationControlName(EStationControl C)
	{
		static const char* Names[] = { "wheel", "jib-sheet", "grinder", "main-sheet", "traveller", "traveller-dump" };
		return int(C) < int(EStationControl::Count) ? Names[int(C)] : "";
	}

	EStationControl StationControlFromName(const std::string& Name)
	{
		for (int I = 0; I < int(EStationControl::Count); ++I) if (Name == StationControlName(EStationControl(I))) return EStationControl(I);
		return EStationControl::Count;
	}

	bool StationOwns(ECrewStation S, EStationControl C)
	{
		switch (S)
		{
		case ECrewStation::None: return true;
		case ECrewStation::Helm: return C == EStationControl::Wheel;
		case ECrewStation::JibTrimmer: return C == EStationControl::JibSheet || C == EStationControl::Grinder;
		case ECrewStation::MainTrimmer: return C == EStationControl::MainSheet || C == EStationControl::Traveller || C == EStationControl::TravellerDump;
		case ECrewStation::Count:
		default: return false;
		}
	}

	FStationConfig FStationConfig::For(const FBoatConfig& Boat)
	{
		// The J/22 stand-in's hardware (a #16 two-speed winch for the jib, a tiller turned into a wheel) by default; a boat
		// with a wheel turns it at her own rate (FBoatConfig::WheelHardOverSeconds).
		FStationConfig C;
		if (Boat.WheelHardOverSeconds > 0.0) C.WheelHardOverSeconds = Boat.WheelHardOverSeconds;
		if (Boat.Type == EBoatType::Maxi)
		{
			// The maxi (prologue step 3): the jib sheet runs to a primary driven by two linked pedestals, which the player
			// grinds with three more grinders (four sprinting at 350 W), through the shafts and the winch's gears (80%).
			// Top gear brings in 1.2 m/s unloaded (big primaries in first gear). With two at 600 W even the luffing J4's
			// 3-4 kN let the sheet in at 0.1 m/s: a minute to get it near home. The J3's and J4's clews (the reefed
			// headsails) sweep about 8 m from hard in to eased; easing round the big drum is 2 m/s (a quarter of the
			// travel a second). The mainsheet and traveller are a pedestal of their own: half the dinghy-sized rates.
			C.GrinderPowerW = 1400.0;
			C.WinchEfficiency = 0.8;
			C.MaxLineSpeedMs = 1.2;
			C.JibSheetTravelM = 8.0;
			C.EaseRate = 0.25;
			C.MainSheetRate = 0.18;
			C.TravellerRate = 0.4;
			// She tacks on the helm and the trim in 30 kn under her gale sails (RunTack: 17 s); the J/22's heavy-air help
			// (the jib let fly early, the main eased through the wind) stops her head to wind.
			C.bTackHelp = false;
		}
		return C;
	}

	FBoatControls FStationControls::Merge(ECrewStation S, const FBoatControls& Player, const FBoatControls& Crew)
	{
		if (S == ECrewStation::None) return Player;
		FBoatControls Out = Crew;
		switch (S)
		{
		case ECrewStation::Helm: Out.Tiller = Player.Tiller; break;
		case ECrewStation::JibTrimmer: Out.JibSheet = Player.JibSheet; Out.bBackJib = Player.bBackJib; break;
		case ECrewStation::MainTrimmer: Out.MainSheet = Player.MainSheet; Out.Traveler = Player.Traveler; break;
		case ECrewStation::None:
		case ECrewStation::Count:
		default: break;
		}
		return Out;
	}

	void FStationControls::Reset(const FBoatModel& Boat, const FBoatControls& Start, ECrewStation S)
	{
		Controls = Crew = Start;
		Station = S;
		TapLeft = 0.0;
		Worked = 0;
		PlayerGrindM = 0.0;
		TackPhase = 0;
		TackTime = 0.0;
		bHoldMain = false;
		CrewTrim.Reset();
		CrewTrim.bHoldMain = false;
		// A boat just reset has no telemetry yet: the crew's course and the wind side wait for the first real angle.
		bCourseSet = false;
		WindSide = 0;
		LastTwaDeg = 0.0;
		Settle(Boat);
	}

	void FStationControls::Settle(const FBoatModel& Boat)
	{
		const double Twa = Boat.GetTelemetry().TrueWindAngle * kRadToDeg;
		if (bCourseSet || std::fabs(Twa) < 1.0) return;
		bCourseSet = true;
		WindSide = Twa >= 0.0 ? 1 : -1;
		LastTwaDeg = Twa;
		CrewHelm.TargetTWADeg = CrewCourse(Twa);
	}

	double FStationControls::CrewCourse(double TwaDeg)
	{
		// Whoever takes the wheel sails her where she is, but no higher than close-hauled (not pinching in a hung tack).
		const double Abs = std::max(std::fabs(TwaDeg), 45.0);
		return TwaDeg >= 0.0 ? Abs : -Abs;
	}

	void FStationControls::MoveTo(const FBoatModel& Boat, ECrewStation S)
	{
		if (S == Station || S == ECrewStation::Count) return;
		// The crew take the wheel on the course she is sailing.
		if (Station == ECrewStation::Helm || Station == ECrewStation::None) CrewHelm.TargetTWADeg = CrewCourse(Boat.GetTelemetry().TrueWindAngle * kRadToDeg);
		Station = S;
		TapLeft = 0.0;
	}

	double FStationControls::SheetLoad(const FBoatModel& Boat) const
	{
		const FBoatTelemetry& T = Boat.GetTelemetry();
		if (T.NumJibStrips > 0)
		{
			Vec3 F;
			for (int I = 0; I < T.NumJibStrips; ++I) F = F + T.JibStrips[I].Force;
			return Config.SheetLoadShare * F.Length();
		}
		// Not stepped yet: the jib's full area at the apparent wind with a lift coefficient of 1.
		return Config.SheetLoadShare * 0.5 * kAirDensity * T.ApparentWindSpeed * T.ApparentWindSpeed * Boat.GetConfig().Jib.TotalArea;
	}

	double FStationControls::GrindLineSpeed(double LoadN, double Effort) const
	{
		const double PowerLimited = Config.WinchEfficiency * Config.GrinderPowerW / std::max(LoadN, 1.0);
		return Clamp(Effort, 0.0, 1.0) * std::min(Config.MaxLineSpeedMs, PowerLimited);
	}

	void FStationControls::Grind(double& Sheet, double Effort, double LoadN, double Dt, bool bPlayer)
	{
		if (Effort <= 0.0 || Sheet <= 0.0) return;
		const double Before = Sheet;
		Sheet = std::max(0.0, Sheet - GrindLineSpeed(LoadN, Effort) * Dt / std::max(Config.JibSheetTravelM, 0.1));
		if (bPlayer && Sheet < Before)
		{
			PlayerGrindM += (Before - Sheet) * Config.JibSheetTravelM;
			Worked |= StationControlBit(EStationControl::Grinder);
		}
	}

	void FStationControls::CallTack()
	{
		if (bHoldMain) return;
		bHoldMain = true;
		HoldFromSide = WindSide;
		HoldTime = HoldSettled = 0.0;
	}

	void FStationControls::TackHelp(const FBoatModel& Boat, FBoatControls& C)
	{
		// The crew's heavy-air tack while the player steers (the J/22 will not tack on the helm alone in 25 kn): as the
		// helm goes down the jib is let fly and the main comes in hard to head her up; through the wind the jib is held
		// aback and the main eased to push the bow down onto the new tack, then the new sheet is ground in.
		const double Twa = Boat.GetTelemetry().TrueWindAngle * kRadToDeg;
		const double Abs = std::fabs(Twa);
		if (TackPhase == 0 && Abs < 40.0 && Controls.Tiller * WindSide > 0.3 && Abs < std::fabs(LastTwaDeg)) { TackPhase = 1; TackTime = 0.0; }
		if (TackPhase == 1 && (Abs > 50.0 || TackTime > 12.0)) TackPhase = 0; // bore away again: no tack
		if (TackPhase == 2 && (Abs >= 35.0 || TackTime > 12.0)) TackPhase = 0;
		if (TackPhase == 1) { C.JibSheet = 1.0; C.MainSheet = 0.0; C.bBackJib = false; }
		if (TackPhase == 2) { C.JibSheet = 1.0; C.MainSheet = 1.0; C.bBackJib = true; }
		if (TackPhase == 0) C.bBackJib = false;
	}

	const FBoatControls& FStationControls::Step(const FBoatModel& Boat, const FStationInput& In, double Dt)
	{
		if (Station == ECrewStation::None) return Controls;
		Settle(Boat);
		const double Twa = Boat.GetTelemetry().TrueWindAngle * kRadToDeg;
		TackTime += Dt;

		// Through the wind (10 degrees past, so a bow hung head to wind does not count): the old jib sheet is let go and
		// the new one is slack until someone grinds it in.
		if (bCourseSet && Twa * WindSide < -10.0)
		{
			WindSide = -WindSide;
			Controls.JibSheet = Crew.JibSheet = 1.0;
			CrewHelm.TargetTWADeg = std::fabs(CrewHelm.TargetTWADeg) * WindSide;
			if (TackPhase == 1) { TackPhase = 2; TackTime = 0.0; }
		}

		// Ready about: the player at the wheel puts it hard over to windward, close-hauled or close to it, and the main is held
		// until she has settled on the new tack, or bears away again on the old one, or 40 s have passed (a hung tack).
		if (Station == ECrewStation::Helm && bCourseSet && std::fabs(Twa) < 70.0 && Controls.Tiller * WindSide > 0.5) CallTack();
		if (bHoldMain)
		{
			HoldTime += Dt;
			const double OnNew = -Twa * HoldFromSide;
			HoldSettled = OnNew > 30.0 && OnNew < 100.0 ? HoldSettled + Dt : 0.0;
			if (HoldSettled >= 1.0 || HoldTime > 40.0 || (HoldTime > 5.0 && Twa * HoldFromSide > 70.0)) bHoldMain = false;
		}
		CrewTrim.bHoldMain = bHoldMain;

		// The crew: everything the player is not holding, from where it is now.
		Crew = Merge(Station, Controls, Crew);
		const double JibBefore = Crew.JibSheet;
		Crew = CrewTrim.Update(Boat, Crew, Dt);
		const double Load = SheetLoad(Boat);
		if (Crew.JibSheet < JibBefore)
		{
			// Trimming the jib in is grinding, for the crew too.
			const double Target = Crew.JibSheet;
			Crew.JibSheet = JibBefore;
			Grind(Crew.JibSheet, Config.CrewGrindEffort, Load, Dt, false);
			Crew.JibSheet = std::max(Crew.JibSheet, Target);
		}
		Crew.Tiller = CrewHelm.Update(Boat);
		if (Station == ECrewStation::Helm && Config.bTackHelp) TackHelp(Boat, Crew);
		else { TackPhase = 0; Crew.bBackJib = false; }

		// The player's hands at their station.
		FBoatControls P = Controls;
		switch (Station)
		{
		case ECrewStation::Helm:
			P.Tiller = Clamp(P.Tiller + Clamp(In.Wheel, -1.0, 1.0) * Dt / std::max(Config.WheelHardOverSeconds, 0.05), -1.0, 1.0);
			if (std::fabs(In.Wheel) > 0.05) Worked |= StationControlBit(EStationControl::Wheel);
			break;
		case ECrewStation::JibTrimmer:
		{
			P.bBackJib = false;
			if (In.JibSheet > 0.0)
			{
				P.JibSheet = std::min(1.0, P.JibSheet + Config.EaseRate * std::min(In.JibSheet, 1.0) * Dt);
				Worked |= StationControlBit(EStationControl::JibSheet);
			}
			TapLeft += In.GrindTaps * Config.GrindTapSeconds;
			double Effort = std::max(Clamp(In.Grind, 0.0, 1.0), Clamp(-In.JibSheet, 0.0, 1.0));
			if (TapLeft > 0.0) { Effort = 1.0; TapLeft = std::max(0.0, TapLeft - Dt); }
			Grind(P.JibSheet, Effort, Load, Dt, true);
			break;
		}
		case ECrewStation::MainTrimmer:
			if (In.MainSheet != 0.0)
			{
				P.MainSheet = Clamp(P.MainSheet + Config.MainSheetRate * Clamp(In.MainSheet, -1.0, 1.0) * Dt, 0.0, 1.0);
				Worked |= StationControlBit(EStationControl::MainSheet);
			}
			if (In.Traveller != 0.0)
			{
				P.Traveler = Clamp(P.Traveler + Config.TravellerRate * Clamp(In.Traveller, -1.0, 1.0) * Dt, -1.0, 1.0);
				Worked |= StationControlBit(EStationControl::Traveller);
			}
			if (In.bTravellerDump)
			{
				P.Traveler = 1.0;
				Worked |= StationControlBit(EStationControl::TravellerDump);
			}
			break;
		case ECrewStation::None:
		case ECrewStation::Count:
		default: break;
		}
		LastTwaDeg = Twa;
		Controls = Merge(Station, P, Crew);
		return Controls;
	}
}
