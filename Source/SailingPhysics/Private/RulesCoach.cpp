#include "RulesCoach.h"
#include "SailingMath.h"
#include <algorithm>
#include <cmath>
#include <cstdio>

namespace Sailing
{
	namespace
	{
		constexpr double kDeg = kPi / 180.0;

		std::string Meters(double M)
		{
			char Buffer[32];
			std::snprintf(Buffer, sizeof(Buffer), "%.0f m", M);
			return Buffer;
		}

		std::string WhatToDo(const FRuleDecision& D, const FVesselSnapshot& Player, const FVesselSnapshot& Other, bool bGiveWay)
		{
			const bool bSail = Player.Status == EVesselStatus::Sailing;
			if (D.GiveWayId == FRuleDecision::Both)
				return "Alter course to starboard, early and plainly, and pass port to port. Sound one short blast if you are under power.";
			if (!bGiveWay)
				return "Hold your course and speed. If she is not keeping clear, sound five short blasts; at close quarters do whatever best avoids collision (Rule 17).";
			switch (D.Encounter)
			{
			case EEncounter::Overtaking:
				return "Keep clear until you are past and clear: pass well off her side, not across her bow.";
			case EEncounter::SailingVessels:
				return D.Rule == std::string("Rule 12(a)(i)")
					? "Bear away early and pass astern of her, or tack well before you get close. Make the change obvious."
					: "You are to windward: head up or slow down and stay well clear of the leeward boat.";
			case EEncounter::Responsibilities:
				if (Other.Status == EVesselStatus::ConstrainedByDraft) return "Get out of the channel and do not impede her: she cannot turn or stop in time.";
				if (Other.Status == EVesselStatus::Anchored) return "Keep clear: she is at anchor.";
				return bSail ? "Change course early to pass well clear, preferably astern of her." : "Alter course to starboard (or slow down) early and substantially, passing astern of her.";
			case EEncounter::Crossing:
				return "Alter course to starboard and pass astern of her, or slow down. Do not cross ahead. One short blast as you turn.";
			default:
				return "Keep clear.";
			}
		}
	}

	std::string FRulesCoach::RelativePosition(double Rel)
	{
		const double A = std::fabs(Rel) / kDeg;
		const char* Side = Rel >= 0.0 ? "starboard" : "port";
		char Buffer[48];
		if (A < 11.25) return "dead ahead";
		if (A > 168.75) return "astern";
		if (A < 67.5) std::snprintf(Buffer, sizeof(Buffer), "on your %s bow", Side);
		else if (A < 112.5) std::snprintf(Buffer, sizeof(Buffer), "abeam to %s", Side);
		else std::snprintf(Buffer, sizeof(Buffer), "on your %s quarter", Side);
		return Buffer;
	}

	void FRulesCoach::Update(double Now, const FVesselSnapshot& Player, const FTrafficSim& Sim)
	{
		const std::vector<FTrafficSim::FPlayerSituation> Situations = Sim.PlayerSituations(3000.0);

		// Collisions involving the player since the last look.
		const std::vector<FTrafficEvent>& Events = Sim.Events();
		for (const FTrafficEvent& E : Events)
		{
			if (E.Time > LastEventTime && E.Type == FTrafficEvent::StandOnAction && E.Other == FTrafficSim::PlayerId)
			{
				for (FEncounter& Enc : Open) if (Enc.Other == E.Vessel) Enc.bOtherActed = true;
			}
			if (E.Time <= LastEventTime || E.Type != FTrafficEvent::Collision) continue;
			if (E.Vessel != FTrafficSim::PlayerId && E.Other != FTrafficSim::PlayerId) continue;
			const int Other = E.Vessel == FTrafficSim::PlayerId ? E.Other : E.Vessel;
			bool bFound = false;
			for (FEncounter& Enc : Open) if (Enc.Other == Other) { Enc.bCollided = true; bFound = true; }
			if (!bFound)
			{
				FEncounter Enc;
				Enc.Other = Other;
				Enc.bGiveWay = E.GiveWayId == FTrafficSim::PlayerId || E.GiveWayId == FRuleDecision::Both;
				Enc.bCollided = true;
				Enc.Rule = "Rule 8";
				Close(Enc, Now);
			}
		}
		if (!Events.empty()) LastEventTime = Events.back().Time;

		// Open an encounter when risk of collision first appears, or when another vessel starts keeping clear of the
		// player (she may act before any risk shows on the present courses).
		for (const FTrafficSim::FPlayerSituation& S : Situations)
		{
			const FTrafficVessel* Other = Sim.Find(S.Other);
			const bool bReacting = Other && (Other->Avoiding == FTrafficSim::PlayerId || (Other->bStandOnAction && Other->ActingFor == FTrafficSim::PlayerId));
			if (!S.Risk.bRisk && !bReacting) continue;
			if (std::any_of(Open.begin(), Open.end(), [&](const FEncounter& E) { return E.Other == S.Other; })) continue;
			FEncounter E;
			E.Other = S.Other;
			E.bBoth = S.Decision.GiveWayId == FRuleDecision::Both;
			E.bGiveWay = S.Decision.IsGiveWay(FTrafficSim::PlayerId);
			E.Rule = S.Decision.Rule;
			E.StartHeading = Player.Heading;
			E.StartSpeed = Player.Speed();
			const FTrafficVessel* V = Sim.Find(S.Other);
			if (V)
			{
				E.OtherName = V->Name;
				E.Safe = SafePassingDistance(Player, V->Snapshot());
			}
			Open.push_back(E);
		}

		// Follow each: how close, and what the player did and when.
		for (size_t I = 0; I < Open.size();)
		{
			FEncounter& E = Open[I];
			const FTrafficSim::FPlayerSituation* S = nullptr;
			for (const FTrafficSim::FPlayerSituation& X : Situations) if (X.Other == E.Other) S = &X;
			if (!S)
			{
				Close(E, Now);
				Open.erase(Open.begin() + I);
				continue;
			}
			E.MinRange = std::min(E.MinRange, S->Risk.Range);
			const double Turn = std::fabs(WrapAngle(Player.Heading - E.StartHeading)) / kDeg;
			const double Slow = E.StartSpeed > 0.5 ? 1.0 - Player.Speed() / E.StartSpeed : 0.0;
			if (S->Risk.Range > 1.5 * E.Safe)
			{
				E.MaxTurnEarly = std::max(E.MaxTurnEarly, Turn);
				E.MaxSlowEarly = std::max(E.MaxSlowEarly, Slow);
			}
			if (S->Risk.Range > 0.6 * E.Safe) E.MaxTurnStandOn = std::max(E.MaxTurnStandOn, Turn);
			// Over when they are past each other and opening, or far apart.
			if ((S->Risk.Tcpa < 0.0 && S->Risk.Range > E.Safe) || S->Risk.Range > 2500.0)
			{
				Close(E, Now);
				Open.erase(Open.begin() + I);
				continue;
			}
			++I;
		}

		// The callout: the most pressing encounter (risk first, then nearest).
		Advice = FAdvice();
		for (const FTrafficSim::FPlayerSituation& S : Situations)
		{
			if (!S.Risk.bRisk && S.Risk.Range > 250.0) continue;
			const FTrafficVessel* V = Sim.Find(S.Other);
			if (!V) continue;
			const FVesselSnapshot O = V->Snapshot();
			Advice.bActive = true;
			Advice.Other = S.Other;
			Advice.Range = S.Risk.Range;
			Advice.Cpa = S.Risk.Cpa;
			Advice.Tcpa = S.Risk.Tcpa;
			Advice.bGiveWay = S.Decision.IsGiveWay(FTrafficSim::PlayerId);
			Advice.bStandOn = !Advice.bGiveWay && S.Decision.GiveWayId >= 0;
			Advice.Who = V->Name + " (" + VesselStatusName(O.Status) + ") " + RelativePosition(S.Risk.RelativeBearing) + ", " + Meters(S.Risk.Range);
			Advice.Role = S.Decision.GiveWayId == FRuleDecision::Both ? "Both give way" : (Advice.bGiveWay ? "You give way" : "You stand on");
			Advice.Rule = S.Decision.Rule;
			Advice.Reason = S.Decision.Reason;
			Advice.Action = S.Risk.bRisk ? WhatToDo(S.Decision, Player, O, Advice.bGiveWay) : "No risk of collision at present: keep a lookout (Rule 5).";
			break;
		}
	}

	void FRulesCoach::Close(const FEncounter& E, double Now)
	{
		FScore S;
		S.Time = Now;
		const std::string Who = E.OtherName.empty() ? std::string("the other vessel") : E.OtherName;
		if (E.bGiveWay || E.bBoth)
		{
			if (E.bCollided) { S.Points = -30; S.Text = "Collision with " + Who + ": you were required to keep clear (" + E.Rule + ")"; }
			else if (E.bOtherActed && E.MaxTurnEarly < 20.0 && E.MaxSlowEarly < 0.4) { S.Points = -10; S.Text = Who + " had to take action to avoid you: you were the give-way vessel (" + E.Rule + ")"; }
			else if (E.MinRange < 0.5 * E.Safe) { S.Points = -10; S.Text = "Too close to " + Who + ": the give-way vessel must keep well clear (" + E.Rule + ", Rule 16)"; }
			else if (E.MaxTurnEarly >= 20.0 || E.MaxSlowEarly >= 0.4) { S.Points = 10; S.Text = "Kept clear of " + Who + " early and plainly (" + E.Rule + ", Rule 16)"; }
			else { S.Points = 5; S.Text = "Kept clear of " + Who + ": next time act earlier and more obviously (Rule 8)"; }
		}
		else
		{
			if (E.bCollided) { S.Points = 0; S.Text = "Collision with " + Who + ": she should have kept clear, and Rule 17(b) asks you to act when she does not"; }
			else if (E.MaxTurnStandOn > 20.0) { S.Points = -5; S.Text = "You were the stand-on vessel: hold course and speed until it is clear she is not acting (Rule 17)"; }
			else { S.Points = 5; S.Text = "Held your course as the stand-on vessel while " + Who + " kept clear (Rule 17)"; }
		}
		Score += S.Points;
		Scores.push_back(S);
		if (Scores.size() > 50) Scores.erase(Scores.begin());
	}
}
