#include "TrafficScenarios.h"
#include "Traffic.h"
#include "Race.h"
#include "Wind.h"
#include <algorithm>
#include <cmath>
#include <random>

namespace Sailing
{
	namespace
	{
		constexpr double kDeg = kPi / 180.0;

		struct FSetup
		{
			ETrafficKind Kind = ETrafficKind::Sailboat;
			double HeadingDeg = 0.0;
			double Speed = 3.0;          // m/s, to place her so she reaches the meeting point on time
			double CruiseFraction = 1.0; // power
			bool bIgnoresRules = false;
			const char* Name = "";
		};

		struct FScenario
		{
			const char* Name;
			const char* Rule;
			FSetup A, B;
			int GiveWay;                 // 0: A, 1: B, 2: both
			bool bExpectSignal;          // the give-way vessel is power-driven and should sound her turn
			bool bStandOnMustAct;        // Rule 17(b): the other ignores the rules
		};

		// Wind from the north (0) at 12 knots. Sailboats: close-hauled about 2.9 m/s at 44 degrees, reaching 3.3.
		const FScenario Scenarios[] = {
			{ "Port tack meets starboard tack", "Rule 12(a)(i)",
				{ ETrafficKind::Sailboat, -44.0, 2.9, 1.0, false, "Starboard J/22" }, { ETrafficKind::Sailboat, 44.0, 2.9, 1.0, false, "Port J/22" }, 1, false, false },
			{ "Same tack: windward keeps clear of leeward", "Rule 12(a)(ii)",
				{ ETrafficKind::Sailboat, -44.0, 2.9, 1.0, false, "Leeward J/22" }, { ETrafficKind::Sailboat, -90.0, 3.3, 1.0, false, "Windward J/22" }, 1, false, false },
			{ "Overtaking: the faster powerboat keeps clear", "Rule 13",
				{ ETrafficKind::Powerboat, 90.0, 2.3, 0.25, false, "Slow runabout" }, { ETrafficKind::Powerboat, 90.0, 9.3, 1.0, false, "Fast runabout" }, 1, true, false },
			{ "A sailboat overtaking a powerboat keeps clear", "Rule 13 before Rule 18",
				{ ETrafficKind::Powerboat, 90.0, 1.2, 0.13, false, "Drifting runabout" }, { ETrafficKind::Sailboat, 90.0, 3.3, 1.0, false, "Reaching J/22" }, 1, false, false },
			{ "Head-on: both alter to starboard", "Rule 14",
				{ ETrafficKind::Powerboat, 0.0, 9.3, 1.0, false, "Northbound runabout" }, { ETrafficKind::Powerboat, 180.0, 9.3, 1.0, false, "Southbound runabout" }, 2, true, false },
			{ "Crossing: give way to the vessel on your starboard side", "Rule 15",
				{ ETrafficKind::Powerboat, 0.0, 9.3, 1.0, false, "Northbound runabout" }, { ETrafficKind::Powerboat, 270.0, 9.3, 1.0, false, "Westbound runabout" }, 0, true, false },
			{ "Power gives way to sail", "Rule 18(a)",
				{ ETrafficKind::Sailboat, 90.0, 3.3, 1.0, false, "Reaching J/22" }, { ETrafficKind::Powerboat, 0.0, 9.3, 1.0, false, "Runabout" }, 1, true, false },
			{ "Sail keeps clear of a vessel engaged in fishing", "Rule 18(b)",
				{ ETrafficKind::Trawler, 90.0, 1.54, 1.0, false, "Shrimp trawler" }, { ETrafficKind::Sailboat, -44.0, 2.9, 1.0, false, "J/22" }, 1, false, false },
			{ "Sail does not impede a ship in the channel", "Rules 9 and 18(d)",
				{ ETrafficKind::Ship, 0.0, 5.1, 1.0, false, "Tanker" }, { ETrafficKind::Sailboat, 90.0, 3.3, 1.0, false, "J/22" }, 1, false, false },
			{ "Stand-on vessel acts when the other does not", "Rule 17(b) and Rule 34(d)",
				{ ETrafficKind::Powerboat, 0.0, 9.3, 1.0, true, "Careless runabout" }, { ETrafficKind::Powerboat, 270.0, 9.3, 1.0, false, "Westbound runabout" }, 0, false, true },
		};
		constexpr int NumScenarios = int(sizeof(Scenarios) / sizeof(Scenarios[0]));

		FWindField ScenarioWind()
		{
			FWindParams P;
			P.SpeedKnots = 12.0;
			P.FromDegrees = 0.0;
			return FWindField(P);
		}

		int Add(FTrafficSim& Sim, const FSetup& S, double MeetX, double MeetY, double Seconds)
		{
			const double H = S.HeadingDeg * kDeg;
			const double X = MeetX - std::cos(H) * S.Speed * Seconds, Y = MeetY - std::sin(H) * S.Speed * Seconds;
			// A waypoint far ahead on the same course: she holds it unless she has to give way.
			const std::vector<std::pair<double, double>> Route = { { X + std::cos(H) * 20000.0, Y + std::sin(H) * 20000.0 } };
			const int Id = S.Kind == ETrafficKind::Sailboat ? Sim.AddSailboat(EBoatType::J22, X, Y, H, Route, S.Name) : Sim.AddPower(S.Kind, X, Y, H, Route, S.Name);
			FTrafficVessel* V = Sim.Find(Id);
			V->CruiseFraction = S.CruiseFraction;
			V->bIgnoresRules = S.bIgnoresRules;
			V->bLoopRoute = false;
			if (!V->IsSail())
			{
				V->Power.Speed = V->Power.OrderedSpeed = S.Speed;
				V->Power.VX = std::cos(H) * S.Speed;
				V->Power.VY = std::sin(H) * S.Speed;
			}
			return Id;
		}

		struct FRun
		{
			double MinRange = 1e9;
			double Turn[2] = { 0.0, 0.0 };
			double TurnBeforeCpa[2] = { 0.0, 0.0 };
			double Slow[2] = { 0.0, 0.0 };
			int Collisions = 0, AiCaused = 0;
			std::vector<std::string> Signals, Events;
		};

		FRun RunPair(const FScenario& S, bool bRules)
		{
			const FWindField Wind = ScenarioWind();
			FTrafficSim Sim;
			Sim.SetWorld(&Wind, nullptr, nullptr);
			Sim.bFollowRules = bRules;
			const double Meet = 100.0;
			const int Ids[2] = { Add(Sim, S.A, 0.0, 0.0, Meet), Add(Sim, S.B, 0.0, 0.0, Meet) };
			const double H0[2] = { S.A.HeadingDeg * kDeg, S.B.HeadingDeg * kDeg };
			const double V0[2] = { S.A.Speed, S.B.Speed };
			FRun R;
			bool bPastCpa = false;
			for (int Frame = 0; Frame < int(240.0 * 30.0); ++Frame)
			{
				Sim.Step(1.0 / 30.0);
				const FVesselSnapshot A = Sim.Find(Ids[0])->Snapshot(), B = Sim.Find(Ids[1])->Snapshot();
				const double Range = std::hypot(A.X - B.X, A.Y - B.Y);
				R.MinRange = std::min(R.MinRange, Range);
				if (AssessRisk(A, B, 1.0).Tcpa < 0.0 && Range > 50.0) bPastCpa = true;
				if (Sim.GetTime() < 5.0) continue; // let the sailboats settle on their course
				for (int K = 0; K < 2; ++K)
				{
					const FVesselSnapshot& V = K == 0 ? A : B;
					const double Turn = std::fabs(WrapAngle(V.Heading - H0[K])) / kDeg;
					R.Turn[K] = std::max(R.Turn[K], Turn);
					if (!bPastCpa) R.TurnBeforeCpa[K] = std::max(R.TurnBeforeCpa[K], Turn);
					R.Slow[K] = std::max(R.Slow[K], 1.0 - V.Speed() / std::max(V0[K], 0.1));
				}
			}
			for (const FTrafficEvent& E : Sim.Events())
			{
				R.Events.push_back(E.Text);
				if (E.Type == FTrafficEvent::Signal) R.Signals.push_back(E.Text);
				if (E.Type == FTrafficEvent::Collision)
				{
					++R.Collisions;
					if (E.GiveWayId != FTrafficSim::PlayerId) ++R.AiCaused;
				}
			}
			return R;
		}

		FRulesScenarioResult RunBusyWater()
		{
			FRulesScenarioResult Out;
			Out.Name = "Busy water: sailboats, runabouts and a trawler for 20 minutes";
			Out.Rule = "All of Part B";
			const FWindField Wind = ScenarioWind();
			FTrafficSim Sim;
			Sim.SetWorld(&Wind, nullptr, nullptr);
			std::mt19937 Rng(11);
			std::uniform_real_distribution<double> U(-900.0, 900.0);
			auto Loop = [&](int N) { std::vector<std::pair<double, double>> R; for (int I = 0; I < N; ++I) R.push_back({ U(Rng), U(Rng) }); return R; };
			for (int I = 0; I < 6; ++I)
			{
				const auto R = Loop(4);
				Sim.AddSailboat(EBoatType::J22, R.back().first, R.back().second, U(Rng) / 300.0, R, "J/22 " + std::to_string(I + 1));
			}
			for (int I = 0; I < 3; ++I)
			{
				const auto R = Loop(5);
				Sim.AddPower(ETrafficKind::Powerboat, R.back().first, R.back().second, U(Rng) / 300.0, R, "Runabout " + std::to_string(I + 1));
			}
			const auto R = Loop(3);
			Sim.AddPower(ETrafficKind::Trawler, R.back().first, R.back().second, 0.0, R, "Trawler");
			for (FTrafficVessel& V : Sim.GetVessels()) if (V.Kind == ETrafficKind::Powerboat) V.CruiseFraction = 0.6;
			double MinRange = 1e9;
			for (int Frame = 0; Frame < int(1200.0 * 30.0); ++Frame)
			{
				Sim.Step(1.0 / 30.0);
				const auto& Vs = Sim.GetVessels();
				for (size_t I = 0; I < Vs.size(); ++I)
					for (size_t J = I + 1; J < Vs.size(); ++J)
					{
						const FVesselSnapshot A = Vs[I].Snapshot(), B = Vs[J].Snapshot();
						MinRange = std::min(MinRange, std::hypot(A.X - B.X, A.Y - B.Y));
					}
			}
			for (const FTrafficEvent& E : Sim.Events())
			{
				if (E.Type == FTrafficEvent::Collision) { ++Out.Collisions; ++Out.AiCausedCollisions; Out.Events.push_back(E.Text); }
				if (E.Type == FTrafficEvent::Signal) Out.Signals.push_back(E.Text);
			}
			Out.bConflict = true;
			Out.MinRange = MinRange;
			Out.bPassed = Out.Collisions == 0;
			if (!Out.bPassed) Out.Failure = std::to_string(Out.Collisions) + " collisions";
			return Out;
		}
	}

	int RulesScenarioCount() { return NumScenarios + 1; }

	FRulesScenarioResult RunRulesScenario(int Index)
	{
		if (Index == NumScenarios) return RunBusyWater();
		const FScenario& S = Scenarios[Index];
		FRulesScenarioResult Out;
		Out.Name = S.Name;
		Out.Rule = S.Rule;
		const FRun Control = RunPair(S, false);
		const FRun Run = RunPair(S, true);
		FVesselSnapshot A, B;
		A.Length = S.A.Kind == ETrafficKind::Sailboat ? 6.86 : FPowerVesselType::For(S.A.Kind).Length;
		B.Length = S.B.Kind == ETrafficKind::Sailboat ? 6.86 : FPowerVesselType::For(S.B.Kind).Length;
		Out.Safe = SafePassingDistance(A, B);
		Out.MinRangeNoRules = Control.MinRange;
		Out.bConflict = Control.MinRange < 0.6 * Out.Safe;
		Out.MinRange = Run.MinRange;
		Out.Collisions = Run.Collisions;
		Out.AiCausedCollisions = Run.AiCaused;
		Out.Signals = Run.Signals;
		Out.Events = Run.Events;
		const int StandOn = S.GiveWay == 0 ? 1 : 0;
		if (S.GiveWay == 2)
		{
			Out.GiveWayTurnDeg = std::min(Run.Turn[0], Run.Turn[1]);
			Out.GiveWaySlowdown = std::min(Run.Slow[0], Run.Slow[1]);
		}
		else
		{
			Out.GiveWayTurnDeg = Run.Turn[S.GiveWay];
			Out.GiveWaySlowdown = Run.Slow[S.GiveWay];
			Out.StandOnTurnDeg = Run.TurnBeforeCpa[StandOn];
		}
		// Pass: a real conflict; resolved without collision at a decent distance; the right vessel acted (turned or
		// slowed substantially); the stand-on vessel held her course (unless she had to act under Rule 17(b));
		// power-driven vessels sounded their turn.
		auto Fail = [&](const std::string& Why) { if (Out.Failure.empty()) Out.Failure = Why; };
		if (!Out.bConflict) Fail("the vessels were not on a collision course to begin with");
		if (Out.Collisions > 0) Fail("collision");
		const double Needed = S.bStandOnMustAct ? 0.2 * Out.Safe : 0.6 * Out.Safe;
		if (Out.MinRange < Needed) Fail("passed too close");
		if (!S.bStandOnMustAct && Out.GiveWayTurnDeg < 10.0 && Out.GiveWaySlowdown < 0.3) Fail("the give-way vessel did not act");
		if (!S.bStandOnMustAct && S.GiveWay != 2 && Out.StandOnTurnDeg > 12.0) Fail("the stand-on vessel did not hold her course");
		if (S.bExpectSignal && Out.Signals.empty()) Fail("no maneuvering signal");
		if (S.bStandOnMustAct)
		{
			bool bFive = false;
			for (const std::string& Sig : Out.Signals) bFive |= Sig.find("Five short") != std::string::npos;
			if (!bFive) Fail("no danger signal (five short blasts)");
		}
		Out.bPassed = Out.Failure.empty();
		return Out;
	}

	FRaceScenarioResult RunAiRace(int Boats, int Laps, double BeatMeters, unsigned Seed)
	{
		FRaceScenarioResult Out;
		const FWindField Wind = ScenarioWind();
		FTrafficSim Sim;
		Sim.SetWorld(&Wind, nullptr, nullptr);
		FRaceRunner Race;
		Race.Course = FRaceCourse::WindwardLeeward(0.0, 0.0, 0.0, BeatMeters, 120.0, Laps);
		Race.TimeLimit = 3600.0;
		std::mt19937 Rng(Seed);
		std::uniform_real_distribution<double> U(-1.0, 1.0);
		for (int I = 0; I < Boats; ++I)
		{
			// Spread out below the line, reaching, 45 m apart as the game lays them out (with some jitter).
			const double X = -160.0 - 30.0 * (I % 2) + 10.0 * U(Rng), Y = (I - 0.5 * (Boats - 1)) * 45.0 + 8.0 * U(Rng);
			const int Id = Sim.AddSailboat(EBoatType::J22, X, Y, 90.0 * kDeg, {}, "J/22 " + std::to_string(I + 1));
			FTrafficVessel* V = Sim.Find(Id);
			V->RaceEntry = Race.AddEntry(Id, V->Name);
		}
		Sim.SetRace(&Race);
		Race.Begin(0.0, 60.0);
		std::vector<bool> Ocs(Race.Entries.size(), false);
		bool bStartSeen = false;
		while (!Race.IsOver() && Sim.GetTime() < Race.StartTime() + Race.TimeLimit + 10.0)
		{
			Sim.Step(1.0 / 30.0);
			if (!bStartSeen && Sim.GetTime() > Race.StartTime() + 0.5)
			{
				bStartSeen = true;
				for (size_t I = 0; I < Race.Entries.size(); ++I) Ocs[I] = Race.Entries[I].bOcs;
			}
		}
		Out.bOver = Race.IsOver();
		Out.RaceSeconds = Sim.GetTime() - Race.StartTime();
		for (size_t I = 0; I < Race.Entries.size(); ++I)
		{
			const FRaceEntry& E = Race.Entries[I];
			FRaceScenarioResult::FBoat B;
			B.Name = E.Name;
			B.Place = E.Place;
			B.Points = E.Points;
			B.Status = E.Status;
			B.FinishSeconds = E.bFinished ? E.FinishTime - Race.StartTime() : 0.0;
			B.MarksRounded = E.NextMark;
			B.bOcsAtStart = Ocs[I];
			Out.Boats.push_back(B);
		}
		for (const auto& Sig : Race.Signals) Out.Signals.push_back(Sig.second);
		for (const FTrafficEvent& E : Sim.Events())
		{
			if (E.Type != FTrafficEvent::Collision) continue;
			++Out.Collisions;
			if (E.GiveWayId != FTrafficSim::PlayerId) ++Out.AiCausedCollisions;
			Out.Signals.push_back(E.Text);
		}
		return Out;
	}
}
