#include "Rules.h"
#include "SailingMath.h"
#include <algorithm>
#include <cmath>

namespace Sailing
{
	namespace
	{
		constexpr double kDeg = kPi / 180.0;
		// Rule 13(b): "coming up with another vessel from a direction more than 22.5 degrees abaft her beam".
		constexpr double kAbaftBeam = 112.5 * kDeg;
		// Head-on (Rule 14): each sees the other ahead or nearly ahead. Six degrees either side is the usual reading.
		constexpr double kHeadOn = 6.0 * kDeg;

		double BearingTo(const FVesselSnapshot& From, const FVesselSnapshot& To)
		{
			return std::atan2(To.Y - From.Y, To.X - From.X);
		}

		/** B is overtaking A: B is abaft A's beam (by more than 22.5 degrees) and closing on her. */
		bool IsOvertaking(const FVesselSnapshot& A, const FVesselSnapshot& B)
		{
			// Overtaking is between vessels underway: a vessel at anchor is not "overtaken" (nor does she overtake).
			if (A.Status == EVesselStatus::Anchored || B.Status == EVesselStatus::Anchored) return false;
			const double Rel = std::fabs(WrapAngle(BearingTo(A, B) - A.Heading));
			if (Rel <= kAbaftBeam) return false;
			// Closing: B's speed along A's course exceeds A's own.
			const double Along = B.VX * std::cos(A.Heading) + B.VY * std::sin(A.Heading);
			return Along > A.Speed() + 0.1;
		}

		/** "the J/22 Kestrel", "the power-driven vessel", or "you" for the player (Id 0 named "You"). */
		std::string Name(const FVesselSnapshot& V)
		{
			if (V.Id == 0 && V.Name && std::string(V.Name) == "You") return "you";
			return "the " + (V.Name && V.Name[0] ? std::string(V.Name) : std::string(VesselStatusName(V.Status)));
		}

		std::string Capital(std::string S)
		{
			if (!S.empty() && S[0] >= 'a' && S[0] <= 'z') S[0] = char(S[0] - 'a' + 'A');
			return S;
		}

		void Decide(FRuleDecision& D, const FVesselSnapshot& GiveWay, const FVesselSnapshot& StandOn)
		{
			D.GiveWayId = GiveWay.Id;
			D.StandOnId = StandOn.Id;
		}
	}

	double FVesselSnapshot::Speed() const { return std::sqrt(VX * VX + VY * VY); }

	const char* VesselStatusName(EVesselStatus Status)
	{
		switch (Status)
		{
		case EVesselStatus::Anchored: return "vessel at anchor";
		case EVesselStatus::NotUnderCommand: return "vessel not under command";
		case EVesselStatus::RestrictedManeuverability: return "vessel restricted in her ability to maneuver";
		case EVesselStatus::ConstrainedByDraft: return "vessel constrained by her draft";
		case EVesselStatus::Fishing: return "vessel engaged in fishing";
		case EVesselStatus::Sailing: return "sailing vessel";
		default: return "power-driven vessel";
		}
	}

	int StatusRank(EVesselStatus Status)
	{
		switch (Status)
		{
		case EVesselStatus::Anchored: return -1;
		case EVesselStatus::NotUnderCommand:
		case EVesselStatus::RestrictedManeuverability: return 0;
		case EVesselStatus::ConstrainedByDraft: return 1;
		case EVesselStatus::Fishing: return 2;
		case EVesselStatus::Sailing: return 3;
		default: return 4;
		}
	}

	double SafePassingDistance(const FVesselSnapshot& A, const FVesselSnapshot& B)
	{
		return Clamp(1.25 * (A.Length + B.Length), 40.0, 400.0);
	}

	FCollisionRisk AssessRisk(const FVesselSnapshot& A, const FVesselSnapshot& B, double SafeDistance, double HorizonSeconds)
	{
		FCollisionRisk R;
		const double DX = B.X - A.X, DY = B.Y - A.Y;
		const double VX = B.VX - A.VX, VY = B.VY - A.VY;
		R.Range = std::sqrt(DX * DX + DY * DY);
		R.RelativeBearing = WrapAngle(std::atan2(DY, DX) - A.Heading);
		const double V2 = VX * VX + VY * VY;
		R.Tcpa = V2 > 1e-6 ? -(DX * VX + DY * VY) / V2 : 0.0;
		const double T = std::max(R.Tcpa, 0.0);
		const double CX = DX + VX * T, CY = DY + VY * T;
		R.Cpa = std::sqrt(CX * CX + CY * CY);
		R.bRisk = (R.Tcpa > 0.0 && R.Tcpa < HorizonSeconds && R.Cpa < SafeDistance) || R.Range < 0.5 * SafeDistance;
		return R;
	}

	const char* EncounterName(EEncounter Encounter)
	{
		switch (Encounter)
		{
		case EEncounter::Overtaking: return "overtaking";
		case EEncounter::Responsibilities: return "responsibilities between vessels";
		case EEncounter::SailingVessels: return "sailing vessels";
		case EEncounter::HeadOn: return "head-on";
		case EEncounter::Crossing: return "crossing";
		default: return "none";
		}
	}

	FRuleDecision DecideRightOfWay(const FVesselSnapshot& A, const FVesselSnapshot& B, double WindFromRad)
	{
		FRuleDecision D;
		// Rule 13 applies "notwithstanding" Rules 4 to 18: any vessel overtaking keeps out of the way.
		if (IsOvertaking(A, B) || IsOvertaking(B, A))
		{
			const bool bBOvertakes = IsOvertaking(A, B);
			const FVesselSnapshot& Over = bBOvertakes ? B : A;
			const FVesselSnapshot& Ahead = bBOvertakes ? A : B;
			D.Encounter = EEncounter::Overtaking;
			D.Rule = "Rule 13";
			Decide(D, Over, Ahead);
			const bool bYou = Name(Over) == "you";
			D.Reason = Capital(Name(Over)) + (bYou ? " are" : " is") + " overtaking (coming up from more than 22.5 degrees abaft the beam), so " + (bYou ? "you keep" : "she keeps")
				+ " clear of " + Name(Ahead) + ", whatever kind of vessel either is.";
			return D;
		}
		// Rule 18: between different kinds, the more maneuverable keeps out of the way.
		const int RA = StatusRank(A.Status), RB = StatusRank(B.Status);
		if (RA != RB)
		{
			const FVesselSnapshot& Low = RA > RB ? A : B;
			const FVesselSnapshot& High = RA > RB ? B : A;
			D.Encounter = EEncounter::Responsibilities;
			D.Rule = High.Status == EVesselStatus::ConstrainedByDraft ? "Rules 9 and 18(d)" : (High.Status == EVesselStatus::Anchored ? "Rules 2 and 8" : "Rule 18");
			Decide(D, Low, High);
			D.Reason = "A " + std::string(VesselStatusName(Low.Status)) + " keeps out of the way of a " + std::string(VesselStatusName(High.Status))
				+ (High.Status == EVesselStatus::ConstrainedByDraft ? ", and must not impede her in the channel." : ".") + " (" + Capital(Name(Low)) + " gives way to " + Name(High) + ".)";
			return D;
		}
		if (A.Status == EVesselStatus::Sailing)
		{
			D.Encounter = EEncounter::SailingVessels;
			if (A.Tack != B.Tack && A.Tack != 0 && B.Tack != 0)
			{
				// Rule 12(a)(i): different tacks, the port-tack boat keeps clear.
				const FVesselSnapshot& Port = A.Tack < 0 ? A : B;
				const FVesselSnapshot& Starboard = A.Tack < 0 ? B : A;
				D.Rule = "Rule 12(a)(i)";
				Decide(D, Port, Starboard);
				D.Reason = "Opposite tacks: " + Name(Port) + " on port tack (wind over the port side) keeps clear of " + Name(Starboard) + " on starboard tack.";
			}
			else
			{
				// Rule 12(a)(ii): same tack, windward keeps clear of leeward. Windward is the one nearer where the wind comes from.
				const double WX = std::cos(WindFromRad), WY = std::sin(WindFromRad);
				const bool bAWindward = A.X * WX + A.Y * WY > B.X * WX + B.Y * WY;
				const FVesselSnapshot& Windward = bAWindward ? A : B;
				const FVesselSnapshot& Leeward = bAWindward ? B : A;
				D.Rule = "Rule 12(a)(ii)";
				Decide(D, Windward, Leeward);
				D.Reason = "Same tack: the windward boat (" + Name(Windward) + ") keeps clear of the leeward boat (" + Name(Leeward) + ").";
			}
			return D;
		}
		// Power-driven (and the other same-kind pairs): head-on or crossing.
		const double RelBofA = WrapAngle(BearingTo(A, B) - A.Heading);
		const double RelAofB = WrapAngle(BearingTo(B, A) - B.Heading);
		if (std::fabs(RelBofA) < kHeadOn && std::fabs(RelAofB) < kHeadOn)
		{
			D.Encounter = EEncounter::HeadOn;
			D.Rule = "Rule 14";
			D.GiveWayId = FRuleDecision::Both;
			D.Reason = "Meeting head-on: each alters course to starboard so they pass port to port.";
			return D;
		}
		// Rule 15: the vessel which has the other on her own starboard side keeps out of the way.
		D.Encounter = EEncounter::Crossing;
		D.Rule = "Rule 15";
		const bool bBOnAStarboard = RelBofA > 0.0;
		const FVesselSnapshot& GiveWay = bBOnAStarboard ? A : B;
		const FVesselSnapshot& StandOn = bBOnAStarboard ? B : A;
		Decide(D, GiveWay, StandOn);
		D.Reason = "Crossing: " + Name(GiveWay) + " (with the other vessel on the starboard side) keeps clear of " + Name(StandOn) + " and avoids crossing ahead.";
		return D;
	}

	const char* SoundSignalMeaning(ESoundSignal Signal)
	{
		switch (Signal)
		{
		case ESoundSignal::OneShort: return "One short blast: I am altering my course to starboard";
		case ESoundSignal::TwoShort: return "Two short blasts: I am altering my course to port";
		case ESoundSignal::ThreeShort: return "Three short blasts: I am operating astern propulsion";
		case ESoundSignal::FiveShort: return "Five short blasts: danger, I doubt you are taking enough action to avoid collision";
		default: return "";
		}
	}

	int SoundSignalBlasts(ESoundSignal Signal)
	{
		switch (Signal)
		{
		case ESoundSignal::OneShort: return 1;
		case ESoundSignal::TwoShort: return 2;
		case ESoundSignal::ThreeShort: return 3;
		case ESoundSignal::FiveShort: return 5;
		default: return 0;
		}
	}
}
