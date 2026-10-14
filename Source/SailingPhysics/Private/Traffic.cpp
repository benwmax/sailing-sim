#include "Traffic.h"
#include "FixedStepper.h"
#include "LakeTerrain.h"
#include "Race.h"
#include "Waves.h"
#include "Wind.h"
#include <algorithm>
#include <cmath>
#include <queue>

namespace Sailing
{
	namespace
	{
		constexpr double kDeg = kPi / 180.0;
		constexpr double kBeatAngle = 44.0 * kDeg;   // close-hauled true wind angle the AI steers
		constexpr double kRunAngle = 155.0 * kDeg;   // deepest angle before gybing (a non-spinnaker boat's best downwind VMG)
		constexpr double kLaylineSlack = 3.0 * kDeg;

		double Bearing(double FromX, double FromY, double ToX, double ToY) { return std::atan2(ToY - FromY, ToX - FromX); }

		FVesselSnapshot WithHeading(FVesselSnapshot S, double Heading, double Speed)
		{
			S.Heading = Heading;
			S.VX = std::cos(Heading) * Speed;
			S.VY = std::sin(Heading) * Speed;
			return S;
		}

		/** Separating-axis test for two hull rectangles (center, heading, length, beam). */
		bool HullsOverlap(const FVesselSnapshot& A, double BeamA, const FVesselSnapshot& B, double BeamB)
		{
			const double AX[2][2] = { { std::cos(A.Heading), std::sin(A.Heading) }, { -std::sin(A.Heading), std::cos(A.Heading) } };
			const double BX[2][2] = { { std::cos(B.Heading), std::sin(B.Heading) }, { -std::sin(B.Heading), std::cos(B.Heading) } };
			const double HA[2] = { 0.5 * A.Length, 0.5 * BeamA }, HB[2] = { 0.5 * B.Length, 0.5 * BeamB };
			const double DX = B.X - A.X, DY = B.Y - A.Y;
			for (int Set = 0; Set < 2; ++Set)
			{
				for (int K = 0; K < 2; ++K)
				{
					const double* Axis = Set == 0 ? AX[K] : BX[K];
					const double Dist = std::fabs(DX * Axis[0] + DY * Axis[1]);
					double R = 0.0;
					for (int J = 0; J < 2; ++J)
					{
						R += HA[J] * std::fabs(AX[J][0] * Axis[0] + AX[J][1] * Axis[1]);
						R += HB[J] * std::fabs(BX[J][0] * Axis[0] + BX[J][1] * Axis[1]);
					}
					if (Dist > R) return false;
				}
			}
			return true;
		}

		std::pair<int, int> PairKey(int A, int B) { return A < B ? std::make_pair(A, B) : std::make_pair(B, A); }
	}

	const char* TrafficKindName(ETrafficKind Kind)
	{
		switch (Kind)
		{
		case ETrafficKind::Sailboat: return "sailboat";
		case ETrafficKind::Powerboat: return "powerboat";
		case ETrafficKind::Trawler: return "shrimp trawler";
		case ETrafficKind::TugAndTow: return "tug with barges";
		case ETrafficKind::Ship: return "ship";
		case ETrafficKind::Committee: return "committee boat";
		}
		return "vessel";
	}

	FPowerVesselType FPowerVesselType::For(ETrafficKind Kind)
	{
		FPowerVesselType T;
		switch (Kind)
		{
		case ETrafficKind::Powerboat:
			T.Length = 6.4; T.Beam = 2.4; T.Draft = 0.6; T.CruiseKnots = 18.0; T.TurnRateDeg = 15.0; T.Accel = 1.5;
			break;
		case ETrafficKind::Trawler:
			// Trawling at 3 knots with her nets out: a vessel engaged in fishing (Rule 26).
			T.Length = 21.0; T.Beam = 6.5; T.Draft = 2.4; T.CruiseKnots = 3.0; T.TurnRateDeg = 4.0; T.Accel = 0.15;
			T.Status = EVesselStatus::Fishing;
			break;
		case ETrafficKind::TugAndTow:
			// A towboat pushing two barges ahead: the length is the whole tow; she cannot turn or stop quickly.
			T.Length = 120.0; T.Beam = 11.0; T.Draft = 2.7; T.CruiseKnots = 6.0; T.TurnRateDeg = 2.0; T.Accel = 0.03;
			T.Status = EVesselStatus::RestrictedManeuverability;
			break;
		case ETrafficKind::Ship:
			// A tanker or container ship in the Houston Ship Channel (45 ft dredged): she cannot leave it.
			T.Length = 230.0; T.Beam = 32.0; T.Draft = 10.5; T.CruiseKnots = 10.0; T.TurnRateDeg = 0.8; T.Accel = 0.02;
			T.Status = EVesselStatus::ConstrainedByDraft;
			break;
		case ETrafficKind::Committee:
			T.Length = 11.0; T.Beam = 3.8; T.Draft = 1.0; T.CruiseKnots = 0.0; T.TurnRateDeg = 0.0; T.Accel = 0.0;
			T.Status = EVesselStatus::Anchored;
			break;
		default:
			break;
		}
		return T;
	}

	void FPowerVessel::Step(double Dt, const Vec3& Current)
	{
		// Turn rate scales with speed through the water (rudder flow), never quite zero (twin screws, bow thruster).
		const double Cruise = std::max(Type.CruiseKnots * kKnot, 0.1);
		const double Rate = Type.TurnRateDeg * kDeg * Clamp(std::fabs(Speed) / Cruise, 0.25, 1.2);
		Heading = WrapAngle(Heading + Clamp(WrapAngle(OrderedHeading - Heading), -Rate * Dt, Rate * Dt));
		Speed += Clamp(OrderedSpeed - Speed, -Type.Accel * Dt, Type.Accel * Dt);
		VX = std::cos(Heading) * Speed + Current.X;
		VY = std::sin(Heading) * Speed + Current.Y;
		X += VX * Dt;
		Y += VY * Dt;
	}

	double FTrafficVessel::Length() const { return IsSail() ? Boat->GetConfig().LengthOverall : Power.Type.Length; }
	double FTrafficVessel::Beam() const { return IsSail() ? Boat->GetConfig().Beam : Power.Type.Beam; }
	double FTrafficVessel::Draft() const { return IsSail() ? Boat->GetConfig().Draft : Power.Type.Draft; }

	FVesselSnapshot FTrafficVessel::Snapshot() const
	{
		FVesselSnapshot S;
		S.Id = Id;
		S.Name = Name.c_str();
		S.Length = Length();
		if (IsSail())
		{
			const FBoatState& St = Boat->GetState();
			const Vec3 O = Boat->OriginPosition();
			S.X = O.X;
			S.Y = O.Y;
			S.VX = St.Velocity.X;
			S.VY = St.Velocity.Y;
			S.Heading = St.Orientation.Heading();
			S.Status = EVesselStatus::Sailing;
			S.Tack = St.WindwardSide;
		}
		else
		{
			S.X = Power.X;
			S.Y = Power.Y;
			S.VX = Power.VX;
			S.VY = Power.VY;
			S.Heading = Power.Heading;
			S.Status = Power.Type.Status;
		}
		return S;
	}

	void FTrafficSim::SetWorld(const FWindField* InWind, const FWaveField* InWaves, const FLakeTerrain* InTerrain, std::function<Vec3(double, double)> InCurrentAt)
	{
		Wind = InWind;
		Waves = InWaves;
		Terrain = InTerrain;
		CurrentAt = std::move(InCurrentAt);
		for (FTrafficVessel& V : Vessels) if (V.Boat) V.Boat->SetTerrain(Terrain);
	}

	int FTrafficSim::AddSailboat(EBoatType Type, double X, double Y, double Heading, std::vector<std::pair<double, double>> Route, const std::string& Name)
	{
		std::shared_ptr<FBoatModel> Model = std::make_shared<FBoatModel>(FBoatConfig::Make(Type));
		Model->Reset(X, Y, Heading, 2.0);
		return AddSailboatModel(Model, std::move(Route), Name);
	}

	void FTrafficSim::Remove(int Id)
	{
		Vessels.erase(std::remove_if(Vessels.begin(), Vessels.end(), [&](const FTrafficVessel& V) { return V.Id == Id; }), Vessels.end());
	}

	int FTrafficSim::AddSailboatModel(std::shared_ptr<FBoatModel> Model, std::vector<std::pair<double, double>> Route, const std::string& Name)
	{
		FTrafficVessel V;
		V.Id = NextId++;
		V.Kind = ETrafficKind::Sailboat;
		V.Name = Name;
		V.Boat = std::move(Model);
		V.Boat->SetTerrain(Terrain);
		V.Boat->GetMutableState().Time = Time;
		const double Heading = V.Boat->GetState().Orientation.Heading(); // telemetry is empty until her first step
		V.Controls.MainSheet = 0.45;
		V.Controls.JibSheet = 0.45;
		V.Route = std::move(Route);
		V.DesiredHeading = V.SteerHeading = Heading;
		V.Side = WrapAngle(WindFrom() - Heading) >= 0.0 ? 1 : -1;
		Vessels.push_back(std::move(V));
		return Vessels.back().Id;
	}

	int FTrafficSim::AddPower(ETrafficKind Kind, double X, double Y, double Heading, std::vector<std::pair<double, double>> Route, const std::string& Name)
	{
		FTrafficVessel V;
		V.Id = NextId++;
		V.Kind = Kind;
		V.Name = Name;
		V.Power.Type = FPowerVesselType::For(Kind);
		V.Power.X = X;
		V.Power.Y = Y;
		V.Power.Heading = V.Power.OrderedHeading = Heading;
		V.Power.Speed = V.Power.OrderedSpeed = V.Power.Type.CruiseKnots * kKnot;
		V.bAnchored = Kind == ETrafficKind::Committee;
		if (V.bAnchored) V.Power.Speed = V.Power.OrderedSpeed = 0.0;
		// Moving from the start (the first look around must see her way on, or an overtaking looks like a crossing).
		V.Power.VX = std::cos(Heading) * V.Power.Speed;
		V.Power.VY = std::sin(Heading) * V.Power.Speed;
		V.Route = std::move(Route);
		V.DesiredHeading = V.SteerHeading = Heading;
		Vessels.push_back(std::move(V));
		return Vessels.back().Id;
	}

	void FTrafficSim::Clear()
	{
		Vessels.clear();
		EventLog.clear();
		Touching.clear();
		LastGiveWay.clear();
		LastContact.clear();
	}

	void FTrafficSim::SetPlayer(const FVesselSnapshot& InPlayer, double Beam, bool bPresent)
	{
		Player = InPlayer;
		Player.Id = PlayerId;
		PlayerBeam = Beam;
		bPlayer = bPresent;
	}

	double FTrafficSim::WindFrom() const
	{
		return Wind ? Wind->GetParams().FromDegrees * kDeg : 0.0;
	}

	double FTrafficSim::LocalWindFrom(double X, double Y) const
	{
		// The wind a helmsman reads there (puffs and shifts), not each few seconds' turbulence.
		if (!Wind) return 0.0;
		double From, Factor;
		Wind->ReadableAt(X, Y, Time, From, Factor);
		return From;
	}

	bool FTrafficSim::WantsShiftTack(const FTrafficVessel& V, double Target) const
	{
		// W1: on a beat, sail the shifts. Headed by more than 7 degrees against the median wind (the boat would point
		// further from the mark than the other tack would), tack; or tack for clearly more wind 200 m along the other tack.
		if (!Wind || Time - V.LastTackTime < 45.0) return false;
		const FVesselSnapshot S = V.Snapshot();
		const double WFL = LocalWindFrom(S.X, S.Y), WFM = WindFrom();
		const double Header = -V.Side * WrapAngle(WFL - WFM);
		// Not on the layline: after tacking the mark must still be upwind of the new tack's course.
		const double NewHeading = WrapAngle(WFL + V.Side * kBeatAngle);
		if (std::fabs(WrapAngle(Target - NewHeading)) > 0.5 * kPi) return false;
		if (Header > 7.0 * kDeg) return true;
		const double Here = WrapAngle(WFL - V.Side * kBeatAngle);
		auto Pressure = [&](double H)
		{
			double From, Factor;
			Wind->ReadableAt(S.X + std::cos(H) * 200.0, S.Y + std::sin(H) * 200.0, Time, From, Factor);
			return Factor;
		};
		return Time - V.LastTackTime > 60.0 && Pressure(NewHeading) > 1.12 * Pressure(Here);
	}

	const FTrafficVessel* FTrafficSim::Find(int Id) const
	{
		for (const FTrafficVessel& V : Vessels) if (V.Id == Id) return &V;
		return nullptr;
	}

	FTrafficVessel* FTrafficSim::Find(int Id)
	{
		for (FTrafficVessel& V : Vessels) if (V.Id == Id) return &V;
		return nullptr;
	}

	std::vector<FVesselSnapshot> FTrafficSim::Snapshots() const
	{
		std::vector<FVesselSnapshot> Out;
		Out.reserve(Vessels.size() + 1);
		for (const FTrafficVessel& V : Vessels) Out.push_back(V.Snapshot());
		if (bPlayer) Out.push_back(Player);
		return Out;
	}

	void FTrafficSim::Emit(FTrafficEvent Event)
	{
		Event.Time = Time;
		EventLog.push_back(std::move(Event));
		if (EventLog.size() > 400) EventLog.erase(EventLog.begin(), EventLog.begin() + 100);
	}

	double FTrafficSim::SailableHeading(const FTrafficVessel& V, double Heading, bool bKeepTack) const
	{
		// W1: close-hauled or as deep as she goes in the wind where she is (a lift lets her point higher).
		const FVesselSnapshot S = V.Snapshot();
		const double WF = LocalWindFrom(S.X, S.Y);
		const double Twa = WrapAngle(WF - Heading); // + = wind from starboard
		const int Side = bKeepTack ? V.Side : (Twa >= 0.0 ? 1 : -1);
		if (std::fabs(Twa) < kBeatAngle) return WrapAngle(WF - Side * kBeatAngle);
		if (std::fabs(Twa) > kRunAngle) return WrapAngle(WF - Side * kRunAngle);
		return Heading;
	}

	void FTrafficSim::Navigate(FTrafficVessel& V)
	{
		const FVesselSnapshot S = V.Snapshot();
		V.SpeedFactor = 1.0;
		if (V.bAnchored) { V.DesiredHeading = S.Heading; return; }
		double Target = S.Heading;
		bool bSlow = false;
		FRaceEntry* Entry = (Race && V.RaceEntry >= 0) ? Race->FindEntry(V.Id) : nullptr;
		if (Entry)
		{
			const FRaceRunner::FTactic T = Race->Tactic(*Entry, S, Time, 3.0);
			Target = T.Heading;
			bSlow = T.bSlow;
		}
		else if (!V.Route.empty())
		{
			const auto& W = V.Route[V.RouteIndex];
			const double Arrive = std::max(40.0, 2.0 * V.Length());
			if (std::hypot(W.first - S.X, W.second - S.Y) < Arrive)
			{
				if (V.RouteIndex + 1 < V.Route.size()) ++V.RouteIndex;
				else if (V.bLoopRoute) V.RouteIndex = 0;
				else { V.bAnchored = true; V.DesiredHeading = S.Heading; return; }
			}
			const auto& Next = V.Route[V.RouteIndex];
			Target = Bearing(S.X, S.Y, Next.first, Next.second);
		}
		if (!V.IsSail())
		{
			V.DesiredHeading = Target;
			V.SpeedFactor = bSlow ? 0.3 : 1.0;
			return;
		}
		// Under sail: beat to windward in tacks and run in gybes, switching at the layline (laylines against the median
		// wind, so a passing shift does not flip her back and forth). W1: upwind she also tacks on the headers and for pressure.
		const double WF = WindFrom();
		const double Twa = WrapAngle(WF - Target);
		const bool bCanTack = Time - V.LastTackTime > 20.0;
		if (std::fabs(Twa) < kBeatAngle)
		{
			const double Rel = WrapAngle(Target - WF); // + = target to the right of the wind
			if (bCanTack && ((V.Side > 0 && Rel > kBeatAngle - kLaylineSlack) || (V.Side < 0 && Rel < -(kBeatAngle - kLaylineSlack))))
			{
				V.Side = -V.Side;
				V.LastTackTime = Time;
			}
			else if (WantsShiftTack(V, Target))
			{
				V.Side = -V.Side;
				V.LastTackTime = Time;
			}
		}
		else if (std::fabs(Twa) > kRunAngle)
		{
			const double Rel = WrapAngle(Target - (WF + kPi));
			const double Off = kPi - kRunAngle;
			if (bCanTack && ((V.Side > 0 && Rel < -(Off - kLaylineSlack)) || (V.Side < 0 && Rel > Off - kLaylineSlack)))
			{
				V.Side = -V.Side;
				V.LastTackTime = Time;
			}
		}
		else
		{
			V.Side = Twa >= 0.0 ? 1 : -1;
		}
		double Heading = SailableHeading(V, Target, true);
		// Shoal water ahead: tack (or gybe) away from it rather than run aground.
		if (Terrain)
		{
			const double Look = std::max(40.0, 5.0 * V.Length());
			const double AX = S.X + std::cos(Heading) * Look, AY = S.Y + std::sin(Heading) * Look;
			if (Terrain->DepthAt(AX, AY) < V.Draft() + 0.5 && Time - V.LastTackTime > 8.0)
			{
				V.Side = -V.Side;
				V.LastTackTime = Time;
				Heading = SailableHeading(V, std::fabs(Twa) < kBeatAngle || std::fabs(Twa) > kRunAngle ? Target : WrapAngle(Target + kPi), true);
			}
		}
		V.DesiredHeading = Heading;
		V.SpeedFactor = bSlow ? 0.3 : 1.0;
	}

	double FTrafficSim::ChooseAvoidance(const FTrafficVessel& V, const FVesselSnapshot& Own, const FVesselSnapshot& Other, double Safe, bool bStarboardOnly, bool& bOutSlow,
		const std::vector<std::pair<FVesselSnapshot, double>>& Nearby) const
	{
		bOutSlow = false;
		const double Speed = std::max(Own.Speed(), V.IsSail() ? 1.5 : 1.0);
		double Best = Own.Heading, BestCost = 1e9, BestCpa = -1.0, BestCpaHeading = Own.Heading;
		// Rule 8: an alteration large enough to be readily apparent (no succession of small ones): at least 30 degrees
		// for a power-driven vessel, 20 under sail, and aiming a third wider than the bare passing distance.
		const double MinTurn = V.IsSail() ? 20.0 : 30.0;
		const double Aim = 1.3 * Safe;
		for (int K = 1; K <= 12; ++K)
		{
			for (int Sign = 1; Sign >= -1; Sign -= 2)
			{
				if (bStarboardOnly && Sign < 0) continue;
				const double Off = Sign * std::max(K * 10.0, MinTurn) * kDeg;
				double H = WrapAngle(Own.Heading + Off);
				if (V.IsSail())
				{
					const double Twa = WrapAngle(WindFrom() - H);
					if (std::fabs(Twa) < kBeatAngle - 2.0 * kDeg) continue; // she cannot sail there
				}
				if (!HeadingClear(V, Own.X, Own.Y, H, Lookahead(V))) continue; // not onto a shoal to keep clear of a boat
				const FVesselSnapshot Trial = WithHeading(Own, H, Speed);
				const FCollisionRisk R = AssessRisk(Trial, Other, Aim);
				if (R.Cpa > BestCpa) { BestCpa = R.Cpa; BestCpaHeading = H; }
				if (R.bRisk) continue;
				// Prefer small turns, turns to starboard for power-driven vessels, and passing astern of the other
				// (Rule 15: avoid crossing ahead) rather than across her bow.
				double Cost = std::fabs(Off) / kDeg;
				if (!V.IsSail() && Sign < 0) Cost += 25.0;
				const double OtherAlong = (Trial.X - Other.X) * std::cos(Other.Heading) + (Trial.Y - Other.Y) * std::sin(Other.Heading);
				if (OtherAlong > 0.0 && Other.Speed() > 0.3)
				{
					// We would be ahead of her when we cross her track: crossing her bow.
					const double T = std::max(R.Tcpa, 0.0);
					const double FX = Trial.X + Trial.VX * T - (Other.X + Other.VX * T), FY = Trial.Y + Trial.VY * T - (Other.Y + Other.VY * T);
					if (FX * std::cos(Other.Heading) + FY * std::sin(Other.Heading) > 0.0) Cost += 30.0;
				}
				// Not into a third vessel: every other boat close by must still pass clear on this course.
				bool bIntoAnother = false;
				for (const auto& N : Nearby)
				{
					if (N.first.Id == Other.Id) continue;
					const FCollisionRisk R2 = AssessRisk(Trial, N.first, 0.7 * N.second, 90.0);
					if (R2.bRisk) { bIntoAnother = true; break; }
				}
				if (bIntoAnother) continue;
				if (Cost < BestCost) { BestCost = Cost; Best = H; }
			}
		}
		if (BestCost < 1e8) return Best;
		bOutSlow = true; // no turn alone does it: slow down (power) or spill wind (sail) as well
		return BestCpaHeading;
	}

	double FTrafficSim::Lookahead(const FTrafficVessel& V) const
	{
		if (V.IsSail()) return std::max(40.0, 5.0 * V.Length());
		return Clamp(V.Power.Type.CruiseKnots * kKnot * 40.0, 3.0 * V.Length(), 700.0);
	}

	bool FTrafficSim::HeadingClear(const FTrafficVessel& V, double X, double Y, double Heading, double Distance) const
	{
		if (!Terrain) return true;
		const double MinDepth = V.Draft() + (V.IsSail() ? 0.5 : std::max(0.4, 0.05 * V.Draft()));
		return TrafficRoutes::ClearPath(*Terrain, X, Y, X + std::cos(Heading) * Distance, Y + std::sin(Heading) * Distance, MinDepth);
	}

	void FTrafficSim::Decide(FTrafficVessel& V)
	{
		DecideCourse(V);
		if (V.IsSail() || V.bAnchored || !Terrain) return;
		// A power-driven vessel keeps to water deep enough for her: if the course she wants runs onto a shoal, she
		// steers the nearest clear course, and stops if there is none.
		const FVesselSnapshot S = V.Snapshot();
		const double Look = Lookahead(V);
		if (HeadingClear(V, S.X, S.Y, V.SteerHeading, Look)) return;
		for (int K = 1; K <= 17; ++K)
		{
			for (int Sign = 1; Sign >= -1; Sign -= 2)
			{
				const double H = WrapAngle(V.SteerHeading + Sign * K * 10.0 * kDeg);
				if (HeadingClear(V, S.X, S.Y, H, Look)) { V.SteerHeading = H; return; }
			}
		}
		V.SpeedFactor = 0.0;
	}

	void FTrafficSim::DecideCourse(FTrafficVessel& V)
	{
		Navigate(V);
		if (V.bAnchored)
		{
			V.SteerHeading = V.DesiredHeading;
			return;
		}
		const FVesselSnapshot Own = V.Snapshot();
		const double Speed = std::max(Own.Speed(), V.IsSail() ? 1.5 : V.Power.Type.CruiseKnots * kKnot * V.CruiseFraction);
		const FVesselSnapshot OwnPlanned = WithHeading(Own, V.DesiredHeading, Speed);
		const double WF = WindFrom();
		const bool bRacing = V.RaceEntry >= 0;

		const bool bWasActing = V.bStandOnAction;
		const FVesselSnapshot* GiveWayTo = nullptr;
		double GiveWaySafe = 0.0, GiveWayTcpa = 1e9;
		bool bHeadOn = false;
		const FVesselSnapshot* StandOnFrom = nullptr;
		FCollisionRisk StandOnRisk;
		double StandOnSafe = 0.0;
		const std::vector<FVesselSnapshot> All = Snapshots();
		std::vector<std::pair<FVesselSnapshot, double>> Nearby;
		for (const FVesselSnapshot& O : All)
		{
			if (O.Id == V.Id || std::hypot(O.X - Own.X, O.Y - Own.Y) > 300.0) continue;
			const FTrafficVessel* OV = O.Id == PlayerId ? nullptr : Find(O.Id);
			Nearby.push_back({ O, (bRacing && OV && OV->RaceEntry >= 0) ? std::max(25.0, 3.5 * Own.Length) : SafePassingDistance(Own, O) });
		}
		for (const FVesselSnapshot& O : All)
		{
			if (O.Id == V.Id) continue;
			const double Range = std::hypot(O.X - Own.X, O.Y - Own.Y);
			if (Range > 4000.0) continue;
			const FTrafficVessel* OV = O.Id == PlayerId ? nullptr : Find(O.Id);
			const bool bBothRacing = bRacing && OV && OV->RaceEntry >= 0;
			// Racing boats sail closer, about three and a half lengths (the AI helms less precisely than a racer), and look
			// only a minute or so ahead in a pack (the racing rules' right of way mirrors Rule 12).
			const double Safe = bBothRacing ? std::max(25.0, 3.5 * Own.Length) : SafePassingDistance(Own, O);
			const double Horizon = bBothRacing ? 75.0 : 480.0;
			// Risk judged on the course she means to sail (so she keeps clear until clear, not just until turned).
			const FCollisionRisk Planned = AssessRisk(OwnPlanned, O, Safe, Horizon);
			const FCollisionRisk Actual = AssessRisk(Own, O, Safe, Horizon);
			// The roles are settled when the risk first appears and kept, for both vessels, until they are past and clear
			// (as Rule 13(d) does for overtaking): after the first turn a head-on meeting looks like a crossing, and
			// re-deciding then would let one boat give up her turn, or let both think they must keep clear.
			const std::pair<int, int> Key = PairKey(V.Id, O.Id);
			auto It = std::find_if(LastGiveWay.begin(), LastGiveWay.end(), [&](const auto& P) { return P.first == Key; });
			const bool bOngoing = It != LastGiveWay.end() && (Actual.Tcpa > 0.0 || Range < Safe);
			if (It != LastGiveWay.end() && !bOngoing) { LastGiveWay.erase(It); It = LastGiveWay.end(); }
			if (!Planned.bRisk && !Actual.bRisk && !bOngoing) continue;
			FRuleDecision D = DecideRightOfWay(Own, O, WF);
			if (It != LastGiveWay.end()) D.GiveWayId = It->second;
			else LastGiveWay.push_back({ Key, D.GiveWayId });
			// Racing rules 21 and 24.2: after the start signal, a boat going back to start (over early, or round an end
			// of the line) and a boat that has finished keep clear of every boat that is still racing.
			if (bBothRacing && Race && Time >= Race->StartTime())
			{
				const FRaceEntry* EV = Race->FindEntry(V.Id);
				const FRaceEntry* EO = Race->FindEntry(O.Id);
				const bool bVOut = EV && (EV->bFinished || EV->bOcs || !EV->bStarted);
				const bool bOOut = EO && (EO->bFinished || EO->bOcs || !EO->bStarted);
				if (bVOut != bOOut)
				{
					D.GiveWayId = bVOut ? V.Id : O.Id;
					D.Rule = (bVOut ? EV : EO)->bFinished ? "RRS 24.2" : "RRS 21";
				}
			}
			// Once she has started keeping clear of a vessel she carries on until they are past and clear (Rule 8(d)),
			// even though her new course no longer shows a risk.
			const bool bStillAvoiding = V.Avoiding == O.Id && bOngoing && D.IsGiveWay(V.Id);
			const bool bStillActing = bWasActing && V.ActingFor == O.Id && bOngoing && !D.IsGiveWay(V.Id);
			if (D.IsGiveWay(V.Id) || bStillAvoiding)
			{
				const double Urgency = bStillAvoiding ? std::max(Actual.Tcpa, 0.0) : Planned.Tcpa;
				if ((Planned.bRisk || bStillAvoiding) && Urgency < GiveWayTcpa)
				{
					GiveWayTo = &O;
					GiveWaySafe = Safe;
					GiveWayTcpa = Urgency;
					bHeadOn = D.GiveWayId == FRuleDecision::Both;
				}
			}
			else if ((Actual.bRisk || bStillActing) && (!StandOnFrom || Actual.Tcpa < StandOnRisk.Tcpa))
			{
				StandOnFrom = &O;
				StandOnRisk = Actual;
				StandOnSafe = Safe;
			}
		}

		V.SteerHeading = V.DesiredHeading;
		V.bStandOnAction = false;
		if (!bFollowRules || V.bIgnoresRules) return;
		if (GiveWayTo)
		{
			bool bSlow = false;
			// Power-driven vessels avoid altering to port for a vessel forward of the beam (Rule 19 spirit, Rule 14 head-on).
			const double H = ChooseAvoidance(V, OwnPlanned, *GiveWayTo, GiveWaySafe, bHeadOn || (!V.IsSail() && !bRacing), bSlow, Nearby);
			V.SteerHeading = V.IsSail() ? SailableHeading(V, H, false) : H;
			// Slow down too if no turn alone does it (power-driven: a sailboat luffing loses her steerage and stalls
			// head to wind as she tries to turn; under sail she keeps clear by her course).
			if (bSlow && !V.IsSail()) V.SpeedFactor = std::min(V.SpeedFactor, 0.35);
			if (V.Avoiding != GiveWayTo->Id)
			{
				V.Avoiding = GiveWayTo->Id;
				const double Turn = WrapAngle(V.SteerHeading - Own.Heading);
				FTrafficEvent E;
				E.Type = FTrafficEvent::GiveWay;
				E.Vessel = V.Id;
				E.Other = GiveWayTo->Id;
				E.Text = V.Name + (std::fabs(Turn) < 5.0 * kDeg ? std::string(" slows") : std::string(Turn > 0.0 ? " alters to starboard" : " alters to port"))
					+ " to keep clear of " + (GiveWayTo->Id == PlayerId ? std::string("you") : std::string(GiveWayTo->Name));
				Emit(E);
				const double SinceSignal = Time - V.LastSignalTime;
				const double Range = std::hypot(GiveWayTo->X - Own.X, GiveWayTo->Y - Own.Y);
				if (!V.IsSail() && std::fabs(Turn) > 10.0 * kDeg && SinceSignal > 15.0 && Range < 3000.0)
				{
					FTrafficEvent S;
					S.Type = FTrafficEvent::Signal;
					S.Vessel = V.Id;
					S.Other = GiveWayTo->Id;
					S.Sound = Turn > 0.0 ? ESoundSignal::OneShort : ESoundSignal::TwoShort;
					S.Text = V.Name + ": " + SoundSignalMeaning(S.Sound);
					Emit(S);
					V.LastSignalTime = Time;
				}
			}
			return;
		}
		V.Avoiding = -1;
		if (StandOnFrom)
		{
			// Rule 17: hold course and speed. Sound the danger signal if the other does not seem to be acting, and at
			// close quarters do whatever best avoids collision (never a turn to port for a vessel on her port side).
			// If the other is visibly keeping clear (turning or slowing for her), hold on longer: two boats maneuvering
			// at once is how they meet. Act only when contact is imminent.
			const FTrafficVessel* GiveWay = StandOnFrom->Id == PlayerId ? nullptr : Find(StandOnFrom->Id);
			const bool bOtherActing = GiveWay && GiveWay->Avoiding == V.Id;
			// Racing (RRS 14 and 16): the right-of-way boat holds her course and acts only to avoid imminent contact.
			const bool bRacingPair = bRacing && GiveWay && GiveWay->RaceEntry >= 0;
			const double Limit = (bOtherActing || bRacingPair) ? 6.0 : (V.IsSail() ? 25.0 : 45.0);
			if (!bOtherActing && !bRacingPair && StandOnRisk.Cpa < 0.5 * StandOnSafe && StandOnRisk.Tcpa < 2.0 * Limit && Time - V.FiveBlastTime > 30.0)
			{
				FTrafficEvent S;
				S.Type = FTrafficEvent::Signal;
				S.Vessel = V.Id;
				S.Other = StandOnFrom->Id;
				S.Sound = ESoundSignal::FiveShort;
				S.Text = V.Name + ": " + SoundSignalMeaning(S.Sound);
				Emit(S);
				V.FiveBlastTime = Time;
			}
			// Once acting she carries on until they are past (no switching back and forth at close quarters).
			const bool bKeepActing = bWasActing && V.ActingFor == StandOnFrom->Id && StandOnRisk.Tcpa > 0.0;
			if (bKeepActing || (StandOnRisk.Cpa < ((bOtherActing || bRacingPair) ? 0.2 : 0.35) * StandOnSafe && StandOnRisk.Tcpa < Limit))
			{
				V.ActingFor = StandOnFrom->Id;
				bool bSlow = false;
				const bool bOtherToPort = StandOnRisk.RelativeBearing < 0.0;
				const double H = ChooseAvoidance(V, Own, *StandOnFrom, 0.6 * StandOnSafe, !V.IsSail() && bOtherToPort, bSlow, Nearby);
				V.SteerHeading = V.IsSail() ? SailableHeading(V, H, false) : H;
				if (!V.IsSail()) V.SpeedFactor = std::min(V.SpeedFactor, bSlow ? 0.0 : 0.5);
				if (!bWasActing)
				{
					FTrafficEvent E;
					E.Type = FTrafficEvent::StandOnAction;
					E.Vessel = V.Id;
					E.Other = StandOnFrom->Id;
					E.Text = V.Name + " takes action to avoid collision (Rule 17(b)): " + (StandOnFrom->Id == PlayerId ? std::string("you") : std::string(StandOnFrom->Name)) + " did not keep clear";
					Emit(E);
				}
				V.bStandOnAction = true;
			}
		}
	}

	void FTrafficSim::Apply(FTrafficVessel& V, double Dt)
	{
		const Vec3 Current = CurrentAt ? CurrentAt(V.IsSail() ? V.Boat->OriginPosition().X : V.Power.X, V.IsSail() ? V.Boat->OriginPosition().Y : V.Power.Y) : Vec3();
		if (!V.IsSail())
		{
			FPowerVessel& P = V.Power;
			P.OrderedHeading = V.SteerHeading;
			const bool bStopped = Time < V.StoppedUntil;
			P.OrderedSpeed = (V.bAnchored || bStopped) ? 0.0 : P.Type.CruiseKnots * kKnot * V.CruiseFraction * V.SpeedFactor;
			P.Step(Dt, V.bAnchored ? Vec3() : Current);
			return;
		}
		FBoatModel& B = *V.Boat;
		B.SetWaterCurrent(Current);
		// W1: the wind she is sailing in (SailableHeading chose the course in it).
		const double Twa = WrapAngle(LocalWindFrom(B.GetState().Position.X, B.GetState().Position.Y) - V.SteerHeading);
		V.Pilot.TargetTWADeg = Clamp(Twa / kDeg, -180.0, 180.0);
		if (std::fabs(V.Pilot.TargetTWADeg) < kBeatAngle / kDeg) V.Pilot.TargetTWADeg = (V.Pilot.TargetTWADeg >= 0.0 ? 1.0 : -1.0) * kBeatAngle / kDeg;
		// A hard tack needs the full rudder.
		V.Pilot.bKeepShortOfStall = std::fabs(WrapAngle(V.SteerHeading - B.GetTelemetry().Heading)) < 40.0 * kDeg;
		V.Controls = V.Trim.Update(B, V.Controls, Dt);
		if (V.SpeedFactor < 0.6 && B.GetState().Velocity.LengthXY() > 1.2)
		{
			// Spill wind: ease both sheets until the sails luff (slackening speed is a way to keep clear too: Rule 8(e)).
			V.Controls.MainSheet = 1.0;
			V.Controls.JibSheet = 1.0;
		}
		V.Controls.Tiller = V.Pilot.Update(B);
		B.Step(Dt, V.Controls, *Wind, Waves);
	}

	std::vector<FObstacleSegment> FTrafficSim::HullsNear(double X, double Y, double Radius, int ExcludeId) const
	{
		std::vector<FObstacleSegment> Out;
		auto AddHull = [&](const FVesselSnapshot& S, double Beam, double Draft)
		{
			if (S.Id == ExcludeId || std::hypot(S.X - X, S.Y - Y) > Radius + 0.5 * S.Length) return;
			const double CH = std::cos(S.Heading), SH = std::sin(S.Heading);
			const double L = 0.5 * S.Length, B = 0.5 * Beam;
			// Pointed bow, square stern: five segments around the outline.
			const double PX[5] = { L, 0.4 * L, -L, -L, 0.4 * L }, PY[5] = { 0.0, B, B, -B, -B };
			for (int I = 0; I < 5; ++I)
			{
				const int J = (I + 1) % 5;
				FObstacleSegment Seg;
				Seg.AX = S.X + PX[I] * CH - PY[I] * SH;
				Seg.AY = S.Y + PX[I] * SH + PY[I] * CH;
				Seg.BX = S.X + PX[J] * CH - PY[J] * SH;
				Seg.BY = S.Y + PX[J] * SH + PY[J] * CH;
				Seg.Radius = 0.15;
				Seg.Bottom = -std::max(Draft, 1.0);
				Seg.Top = 3.0;
				Seg.VX = S.VX;
				Seg.VY = S.VY;
				Out.push_back(Seg);
			}
		};
		for (const FTrafficVessel& V : Vessels) AddHull(V.Snapshot(), V.Beam(), V.Draft());
		if (bPlayer) AddHull(Player, PlayerBeam, 1.2);
		return Out;
	}

	std::vector<FTrafficSim::FPlayerSituation> FTrafficSim::PlayerSituations(double MaxRange) const
	{
		std::vector<FPlayerSituation> Out;
		if (!bPlayer) return Out;
		for (const FTrafficVessel& V : Vessels)
		{
			const FVesselSnapshot O = V.Snapshot();
			if (std::hypot(O.X - Player.X, O.Y - Player.Y) > MaxRange) continue;
			FPlayerSituation S;
			S.Other = V.Id;
			S.Risk = AssessRisk(Player, O, SafePassingDistance(Player, O));
			S.Decision = DecideRightOfWay(Player, O, WindFrom());
			Out.push_back(S);
		}
		std::sort(Out.begin(), Out.end(), [](const FPlayerSituation& A, const FPlayerSituation& B)
		{
			if (A.Risk.bRisk != B.Risk.bRisk) return A.Risk.bRisk;
			return A.Risk.Range < B.Risk.Range;
		});
		return Out;
	}

	void FTrafficSim::DetectCollisions()
	{
		const std::vector<FVesselSnapshot> All = Snapshots();
		auto BeamOf = [&](int Id) { if (Id == PlayerId) return PlayerBeam; const FTrafficVessel* V = Find(Id); return V ? V->Beam() : 2.0; };
		std::vector<std::pair<int, int>> Now;
		for (size_t I = 0; I < All.size(); ++I)
		{
			for (size_t J = I + 1; J < All.size(); ++J)
			{
				const FVesselSnapshot& A = All[I];
				const FVesselSnapshot& B = All[J];
				if (std::hypot(A.X - B.X, A.Y - B.Y) > 0.5 * (A.Length + B.Length) + 1.0) continue;
				if (!HullsOverlap(A, BeamOf(A.Id), B, BeamOf(B.Id))) continue;
				const std::pair<int, int> Key = PairKey(A.Id, B.Id);
				Now.push_back(Key);
				if (std::find(Touching.begin(), Touching.end(), Key) != Touching.end())
				{
					// Still alongside: the crews fend off. Ease AI sailboats apart (about half a meter a second) so two
					// hulls can never lock together; the player's boat is never moved.
					const double DX = A.X - B.X, DY = A.Y - B.Y, D = std::max(std::hypot(DX, DY), 0.1);
					for (const FVesselSnapshot* S : { &A, &B })
					{
						FTrafficVessel* V = Find(S->Id);
						if (!V || !V->IsSail()) continue;
						const double Sign = S == &A ? 1.0 : -1.0;
						V->Boat->GetMutableState().Position.X += Sign * DX / D * 0.017;
						V->Boat->GetMutableState().Position.Y += Sign * DY / D * 0.017;
					}
					continue;
				}
				// One incident between two boats is one collision, however often they touch in the next few seconds.
				auto Last = std::find_if(LastContact.begin(), LastContact.end(), [&](const auto& P) { return P.first == Key; });
				const bool bRepeat = Last != LastContact.end() && Time - Last->second < 20.0;
				if (Last != LastContact.end()) Last->second = Time; else LastContact.push_back({ Key, Time });
				if (bRepeat) continue;
				FTrafficEvent E;
				E.Type = FTrafficEvent::Collision;
				E.Vessel = Key.first;
				E.Other = Key.second;
				auto It = std::find_if(LastGiveWay.begin(), LastGiveWay.end(), [&](const auto& P) { return P.first == Key; });
				E.GiveWayId = It != LastGiveWay.end() ? It->second : DecideRightOfWay(A, B, WindFrom()).GiveWayId;
				E.Text = std::string("Collision: ") + (A.Id == PlayerId ? "you" : A.Name) + " and " + (B.Id == PlayerId ? "you" : B.Name);
				Emit(E);
				// Power vessels stop their engines after a collision.
				for (int Id : { A.Id, B.Id })
				{
					if (FTrafficVessel* V = Find(Id)) if (!V->IsSail()) V->StoppedUntil = Time + 10.0;
				}
			}
		}
		Touching = std::move(Now);
	}

	void FTrafficSim::Step(double Dt)
	{
		if (!Wind) return;
		Accumulator += std::min(Dt, 0.25);
		int Steps = 0;
		std::vector<FTrafficVessel*> Sails;
		if (ParallelFor) for (FTrafficVessel& V : Vessels) if (V.IsSail()) Sails.push_back(&V);
		while (Accumulator >= PhysicsDt)
		{
			Accumulator -= PhysicsDt;
			Time += PhysicsDt;
			if (Time >= NextDecision)
			{
				NextDecision = Time + DecisionInterval;
				for (FTrafficVessel& V : Vessels) Decide(V);
				if (Race) Race->Update(Time, Snapshots());
				// Other hulls nearby for each sailboat's contact physics.
				for (FTrafficVessel& V : Vessels)
				{
					if (!V.IsSail()) continue;
					const Vec3 O = V.Boat->OriginPosition();
					V.Boat->SetMovingObstacles(HullsNear(O.X, O.Y, 40.0, V.Id));
				}
			}
			if (ParallelFor && Sails.size() > 1)
			{
				for (FTrafficVessel& V : Vessels) if (!V.IsSail()) Apply(V, PhysicsDt);
				ParallelFor(int(Sails.size()), [this, &Sails](int K) { Apply(*Sails[K], PhysicsDt); });
			}
			else
			{
				for (FTrafficVessel& V : Vessels) Apply(V, PhysicsDt);
			}
			if (++Steps % 4 == 0) DetectCollisions();
		}
	}

	namespace TrafficRoutes
	{
		bool ClearPath(const FLakeTerrain& Terrain, double AX, double AY, double BX, double BY, double MinDepth)
		{
			const double Len = std::hypot(BX - AX, BY - AY);
			const int N = std::max(1, int(Len / 15.0));
			for (int I = 0; I <= N; ++I)
			{
				const double T = double(I) / N;
				if (Terrain.DepthAt(AX + (BX - AX) * T, AY + (BY - AY) * T) < MinDepth) return false;
			}
			return true;
		}

		bool DeepPoint(const FLakeTerrain& Terrain, std::mt19937& Rng, double CX, double CY, double Radius, double MinDepth, double& OutX, double& OutY)
		{
			std::uniform_real_distribution<double> U(0.0, 1.0);
			for (int Try = 0; Try < 400; ++Try)
			{
				const double R = Radius * std::sqrt(U(Rng)), A = 2.0 * kPi * U(Rng);
				const double X = CX + R * std::cos(A), Y = CY + R * std::sin(A);
				if (Terrain.DepthAt(X, Y) >= MinDepth) { OutX = X; OutY = Y; return true; }
			}
			return false;
		}

		std::vector<std::pair<double, double>> RandomLoop(const FLakeTerrain& Terrain, std::mt19937& Rng, double X, double Y, double Radius, double MinDepth, int Count)
		{
			std::vector<std::pair<double, double>> Route;
			double PX = X, PY = Y;
			for (int Try = 0; Try < 200 && int(Route.size()) < Count; ++Try)
			{
				double NX, NY;
				if (!DeepPoint(Terrain, Rng, X, Y, Radius, MinDepth, NX, NY)) break;
				if (std::hypot(NX - PX, NY - PY) < 0.25 * Radius || !ClearPath(Terrain, PX, PY, NX, NY, MinDepth)) continue;
				const bool bLast = int(Route.size()) == Count - 1;
				if (bLast && !ClearPath(Terrain, NX, NY, X, Y, MinDepth)) continue;
				Route.push_back({ NX, NY });
				PX = NX;
				PY = NY;
			}
			Route.push_back({ X, Y });
			return Route;
		}

		std::vector<std::pair<double, double>> DeepWaterPath(const FLakeTerrain& Terrain, double AX, double AY, double BX, double BY, double MinDepth, double Cell)
		{
			std::vector<std::pair<double, double>> Path;
			const double X0 = Terrain.GetOriginX(), Y0 = Terrain.GetOriginY();
			const int Rows = int(Terrain.GetRows() * Terrain.GetCell() / Cell) + 1, Cols = int(Terrain.GetCols() * Terrain.GetCell() / Cell) + 1;
			auto Index = [&](double X, double Y) { return std::make_pair(int(std::lround((X - X0) / Cell)), int(std::lround((Y - Y0) / Cell))); };
			auto Center = [&](int R, int C) { return std::make_pair(X0 + R * Cell, Y0 + C * Cell); };
			// Ends beyond the grid (a station up the channel past the baked area) are brought to its edge first.
			auto Clamped = [&](double X, double Y) { const auto P = Index(X, Y); return std::make_pair(std::clamp(P.first, 0, Rows - 1), std::clamp(P.second, 0, Cols - 1)); };
			const auto [SR, SC] = Clamped(AX, AY);
			const auto [GR, GC] = Clamped(BX, BY);
			std::vector<uint8_t> Deep(size_t(Rows) * Cols, 0);
			for (int R = 0; R < Rows; ++R)
				for (int C = 0; C < Cols; ++C)
				{
					const auto P = Center(R, C);
					Deep[size_t(R) * Cols + C] = Terrain.DepthAt(P.first, P.second) >= MinDepth;
				}
			// The ends may be on a pier or a shoal beside the channel: move each to the nearest deep cell within 3 km.
			auto Snap = [&](int& R, int& C)
			{
				if (Deep[size_t(R) * Cols + C]) return true;
				const int Reach = int(3000.0 / Cell);
				int BestR = -1, BestC = -1, BestD = 1 << 30;
				for (int DR = -Reach; DR <= Reach; ++DR)
					for (int DC = -Reach; DC <= Reach; ++DC)
					{
						const int NR = R + DR, NC = C + DC;
						if (NR < 0 || NC < 0 || NR >= Rows || NC >= Cols || !Deep[size_t(NR) * Cols + NC]) continue;
						if (DR * DR + DC * DC < BestD) { BestD = DR * DR + DC * DC; BestR = NR; BestC = NC; }
					}
				if (BestR < 0) return false;
				R = BestR;
				C = BestC;
				return true;
			};
			int StartR = SR, StartC = SC, GoalR = GR, GoalC = GC;
			if (!Snap(StartR, StartC) || !Snap(GoalR, GoalC)) return Path;
			// A* with 8 neighbors.
			std::vector<float> Cost(Deep.size(), 1e30f);
			std::vector<int> From(Deep.size(), -1);
			using FNode = std::pair<float, int>;
			std::priority_queue<FNode, std::vector<FNode>, std::greater<FNode>> Open;
			const int Start = StartR * Cols + StartC, Goal = GoalR * Cols + GoalC;
			Cost[Start] = 0.0f;
			Open.push({ 0.0f, Start });
			while (!Open.empty())
			{
				const int N = Open.top().second;
				Open.pop();
				if (N == Goal) break;
				const int R = N / Cols, C = N % Cols;
				for (int DR = -1; DR <= 1; ++DR)
					for (int DC = -1; DC <= 1; ++DC)
					{
						if (!DR && !DC) continue;
						const int NR = R + DR, NC = C + DC;
						if (NR < 0 || NC < 0 || NR >= Rows || NC >= Cols) continue;
						const int M = NR * Cols + NC;
						if (!Deep[M]) continue;
						const float G = Cost[N] + ((DR && DC) ? 1.4142f : 1.0f);
						if (G < Cost[M])
						{
							Cost[M] = G;
							From[M] = N;
							const float H = float(std::hypot(double(NR - GoalR), double(NC - GoalC)));
							Open.push({ G + H, M });
						}
					}
			}
			if (From[Goal] < 0 && Goal != Start) return Path;
			std::vector<std::pair<double, double>> Raw;
			for (int N = Goal; N >= 0; N = From[N]) Raw.push_back(Center(N / Cols, N % Cols));
			std::reverse(Raw.begin(), Raw.end());
			// (The ends stay on the snapped deep cells: the ship turns at the channel, not on the pier.)
			// Straighten: from each kept point, jump to the farthest point still reachable in a clear line.
			size_t I = 0;
			Path.push_back(Raw[0]);
			while (I + 1 < Raw.size())
			{
				size_t J = Raw.size() - 1;
				while (J > I + 1 && !ClearPath(Terrain, Raw[I].first, Raw[I].second, Raw[J].first, Raw[J].second, MinDepth)) --J;
				Path.push_back(Raw[J]);
				I = J;
			}
			return Path;
		}
	}
}
