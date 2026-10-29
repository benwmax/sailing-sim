#include "ReferenceChecks.h"
#include "AutoTrim.h"
#include "FixedStepper.h"
#include "PolarReference.h"
#include "Waves.h"
#include "Wind.h"
#include <algorithm>
#include <cmath>
#include <cstdio>

namespace Sailing
{
	namespace
	{
		struct FRunResult { double MeanKnots = 0.0, PeakKnots = 0.0, MeanHeelDeg = 0.0, MeanTwaDeg = 0.0, MeanLeewayDeg = 0.0, MaxTiltDeg = 0.0; };

		/** The polar's way of sailing a point (autopilot, auto-trim, crew already hiking), with reefs, gusts and a fetch. */
		FRunResult SteadyRun(const FBoatConfig& Config, double Tws, double Twa, bool bSpinnaker, int Reefs, double Settle, double Average,
			double Gust = 0.0, double Fetch = kPolarFetchMeters, uint32_t Seed = 1)
		{
			FWindParams WindParams;
			WindParams.SpeedKnots = Tws;
			WindParams.GustIntensity = Gust;
			WindParams.ShiftDegrees = Gust > 0.0 ? 4.0 : 0.0;
			WindParams.Seed = Seed;
			const FWindField Wind(WindParams);
			FWaveField Waves(7);
			FWaveParams WaveParams;
			WaveParams.WindSpeedKnots = Tws;
			WaveParams.FetchMeters = Fetch;
			WaveParams.bCalibrationSea = true;
			Waves.SetWind(WaveParams);
			Waves.SnapToTarget();

			FBoatModel Boat(Config);
			Boat.Reset(0.0, 0.0, -Twa * kDegToRad, 0.6 * Tws * kKnot);
			const int Windward = Twa >= 0.0 ? 1 : -1;
			Boat.GetMutableState().WindwardSide = Windward;
			Boat.GetMutableState().CrewOffset = Windward * Config.CrewSitOut;
			FAutopilot Pilot;
			Pilot.TargetTWADeg = Twa;
			FAutoTrim Trim;
			FBoatControls C;
			C.MainSheet = C.JibSheet = Clamp(std::fabs(Twa) / 180.0, 0.0, 1.0);
			C.bSpinnaker = bSpinnaker && Config.HasSpinnaker();
			C.Hike = Clamp((Tws - 6.0) / 6.0, 0.0, 1.0) * (1.0 - SmoothStep(95.0, 115.0, std::fabs(Twa)));
			C.SpinSheet = 0.5;
			C.Reef = Reefs;
			FRunResult R;
			const int SettleSteps = int(Settle * PhysicsHz), AverageSteps = int(Average * PhysicsHz);
			// Peaks as a GPS logs them: the best one-second mean (a single physics step catches every wave's orbital surge).
			const int Window = int(PhysicsHz);
			std::vector<double> Last(Window, 0.0);
			double WindowSum = 0.0;
			for (int I = 0; I < SettleSteps + AverageSteps; ++I)
			{
				C = Trim.Update(Boat, C, PhysicsDt);
				C.Tiller = Pilot.Update(Boat);
				C.Reef = Reefs;
				Boat.Step(PhysicsDt, C, Wind, &Waves);
				if (I >= SettleSteps)
				{
					const FBoatTelemetry& T = Boat.GetTelemetry();
					R.MeanKnots += T.BoatSpeed / kKnot;
					const int K = (I - SettleSteps) % Window;
					WindowSum += T.BoatSpeed / kKnot - Last[K];
					Last[K] = T.BoatSpeed / kKnot;
					if (I - SettleSteps >= Window - 1) R.PeakKnots = std::max(R.PeakKnots, WindowSum / Window);
					R.MeanHeelDeg += std::fabs(T.Heel) * kRadToDeg;
					R.MeanTwaDeg += std::fabs(T.TrueWindAngle) * kRadToDeg;
					R.MeanLeewayDeg += std::fabs(T.Leeway) * kRadToDeg;
					R.MaxTiltDeg = std::max(R.MaxTiltDeg, Boat.GetState().Orientation.Tilt() * kRadToDeg);
				}
			}
			R.MeanKnots /= AverageSteps;
			R.MeanHeelDeg /= AverageSteps;
			R.MeanTwaDeg /= AverageSteps;
			R.MeanLeewayDeg /= AverageSteps;
			return R;
		}

		FReferenceCheck Check(const char* Group, const std::string& Name, double Value, double Low, double High, const char* Unit, const char* Source)
		{
			FReferenceCheck C;
			C.Group = Group;
			C.Name = Name;
			C.Value = Value;
			C.Low = Low;
			C.High = High;
			C.Unit = Unit;
			C.Source = Source;
			return C;
		}

		std::string Fmt(const char* Format, double A, double B = 0.0)
		{
			char Buf[160];
			std::snprintf(Buf, sizeof(Buf), Format, A, B);
			return Buf;
		}
	}

	double ManeuverLossSeconds(const FBoatConfig& Config, double TrueWindKnots, bool bTack)
	{
		const FVmgResult Best = bTack ? BestUpwind(Config, TrueWindKnots) : BestDownwind(Config, TrueWindKnots);
		const double Twa = Best.TwaDeg;
		FWindParams WindParams;
		WindParams.SpeedKnots = TrueWindKnots;
		const FWindField Wind(WindParams);
		FWaveField Waves(7);
		FWaveParams WaveParams;
		WaveParams.WindSpeedKnots = TrueWindKnots;
		WaveParams.FetchMeters = kPolarFetchMeters;
		WaveParams.bCalibrationSea = true;
		Waves.SetWind(WaveParams);
		Waves.SnapToTarget();
		FBoatModel Boat(Config);
		Boat.Reset(0.0, 0.0, -Twa * kDegToRad, 0.6 * TrueWindKnots * kKnot);
		Boat.GetMutableState().WindwardSide = 1;
		Boat.GetMutableState().CrewOffset = Config.CrewSitOut;
		FAutopilot Pilot;
		Pilot.TargetTWADeg = Twa;
		FAutoTrim Trim;
		Trim.Settings.bHands = false;
		FBoatControls C;
		C.MainSheet = C.JibSheet = Clamp(Twa / 180.0, 0.0, 1.0);
		C.Hike = Clamp((TrueWindKnots - 6.0) / 6.0, 0.0, 1.0) * (1.0 - SmoothStep(95.0, 115.0, Twa));
		// Progress along the wind: up it beating (+X, the wind is from the north), down it running.
		const double Along = bTack ? 1.0 : -1.0;
		auto Run = [&](double Seconds)
		{
			for (int I = 0; I < int(Seconds * PhysicsHz); ++I)
			{
				C = Trim.Update(Boat, C, PhysicsDt);
				C.Tiller = Pilot.Update(Boat);
				Boat.Step(PhysicsDt, C, Wind, &Waves);
			}
		};
		Run(30.0);
		const double X0 = Boat.GetState().Position.X;
		Run(10.0);
		const double Vmg = Along * (Boat.GetState().Position.X - X0) / 10.0;
		const double X1 = Boat.GetState().Position.X;
		Pilot.TargetTWADeg = -Twa;
		Pilot.MaxTiller = 0.8;
		Pilot.bKeepShortOfStall = false;
		Run(40.0);
		const double Progress = Along * (Boat.GetState().Position.X - X1);
		return Vmg > 0.05 ? 40.0 - Progress / Vmg : 40.0;
	}

	FVmgResult BestUpwind(const FBoatConfig& Config, double TrueWindKnots)
	{
		// VMG is flat near its best angle, so the single best sample jumps about with noise: fit a parabola through the
		// best point and its neighbours and take its peak.
		std::vector<double> Twas, Vmgs;
		std::vector<FRunResult> Runs;
		for (double Twa = 34.0; Twa <= 58.0; Twa += 2.0)
		{
			const FRunResult R = SteadyRun(Config, TrueWindKnots, Twa, false, 0, 25.0, 10.0);
			// Made good over the ground: leeway carries her that much further off the wind than she is heading.
			Twas.push_back(R.MeanTwaDeg);
			Vmgs.push_back(R.MeanKnots * std::cos((R.MeanTwaDeg + R.MeanLeewayDeg) * kDegToRad));
			Runs.push_back(R);
		}
		size_t I = size_t(std::max_element(Vmgs.begin(), Vmgs.end()) - Vmgs.begin());
		FVmgResult Best;
		Best.TwaDeg = Twas[I]; Best.SpeedKnots = Runs[I].MeanKnots; Best.VmgKnots = Vmgs[I]; Best.HeelDeg = Runs[I].MeanHeelDeg;
		// Least-squares parabola through every sample within 8 degrees of the best one (in u = TWA - best, for conditioning).
		double S0 = 0, S1 = 0, S2 = 0, S3 = 0, S4 = 0, T0 = 0, T1 = 0, T2 = 0;
		for (size_t K = 0; K < Vmgs.size(); ++K)
		{
			const double U = Twas[K] - Twas[I];
			if (std::fabs(U) > 8.5) continue;
			S0 += 1; S1 += U; S2 += U * U; S3 += U * U * U; S4 += U * U * U * U;
			T0 += Vmgs[K]; T1 += U * Vmgs[K]; T2 += U * U * Vmgs[K];
		}
		// Normal equations for y = a u^2 + b u + c (Cramer's rule).
		const double D = S4 * (S2 * S0 - S1 * S1) - S3 * (S3 * S0 - S1 * S2) + S2 * (S3 * S1 - S2 * S2);
		if (S0 >= 4 && std::fabs(D) > 1e-12)
		{
			const double A = (T2 * (S2 * S0 - S1 * S1) - S3 * (T1 * S0 - S1 * T0) + S2 * (T1 * S1 - S2 * T0)) / D;
			const double B = (S4 * (T1 * S0 - S1 * T0) - T2 * (S3 * S0 - S1 * S2) + S2 * (S3 * T0 - T1 * S2)) / D;
			if (A < 0.0) Best.TwaDeg = Twas[I] + Clamp(-B / (2.0 * A), -8.0, 8.0);
		}
		return Best;
	}

	FVmgResult BestDownwind(const FBoatConfig& Config, double TrueWindKnots)
	{
		FVmgResult Best;
		for (double Twa = 130.0; Twa <= 175.0; Twa += 7.5)
		{
			const FRunResult R = SteadyRun(Config, TrueWindKnots, Twa, false, 0, 25.0, 10.0);
			const double Vmg = -R.MeanKnots * std::cos(R.MeanTwaDeg * kDegToRad);
			if (Vmg > Best.VmgKnots) { Best.TwaDeg = R.MeanTwaDeg; Best.SpeedKnots = R.MeanKnots; Best.VmgKnots = Vmg; Best.HeelDeg = R.MeanHeelDeg; }
		}
		return Best;
	}

	double RollPeriodSeconds(const FBoatConfig& Config, double StartHeelDeg)
	{
		// At the dock: no wind, no waves, sails eased, the boat heeled and let go. Period from the zero crossings.
		FWindParams Calm;
		Calm.SpeedKnots = 0.0;
		const FWindField Wind(Calm);
		FBoatModel Boat(Config);
		Boat.Reset(0.0, 0.0, 0.0, 0.0);
		// Let her settle upright at her waterline first, then heel her (positive heel = starboard side up).
		FBoatControls C;
		C.MainSheet = C.JibSheet = 1.0;
		for (int I = 0; I < int(5.0 * PhysicsHz); ++I) Boat.Step(PhysicsDt, C, Wind);
		// She lists a little with the crew sitting to one side: oscillate about that.
		const double Rest = Boat.GetTelemetry().Heel;
		FBoatState& S = Boat.GetMutableState();
		S.Orientation = Quat::FromAxisAngle({ 1, 0, 0 }, -StartHeelDeg * kDegToRad) * S.Orientation;
		S.AngularVelocity = Vec3();
		double LastHeel = Boat.GetTelemetry().Heel - Rest, FirstCross = -1.0, LastCross = -1.0;
		int Crossings = 0;
		for (int I = 0; I < int(12.0 * PhysicsHz); ++I)
		{
			Boat.Step(PhysicsDt, C, Wind);
			const double Heel = Boat.GetTelemetry().Heel - Rest;
			if ((Heel > 0.0) != (LastHeel > 0.0) && I > 2)
			{
				const double T = I * PhysicsDt;
				if (FirstCross < 0.0) FirstCross = T;
				LastCross = T;
				++Crossings;
			}
			LastHeel = Heel;
		}
		return Crossings >= 3 ? 2.0 * (LastCross - FirstCross) / (Crossings - 1) : -1.0;
	}

	double HeelAfterCapsize(const FBoatConfig& Config, double StartHeelDeg, double TrueWindKnots, double Seconds)
	{
		FWindParams WindParams;
		WindParams.SpeedKnots = TrueWindKnots;
		const FWindField Wind(WindParams);
		FWaveField Waves(7);
		FWaveParams WaveParams;
		WaveParams.WindSpeedKnots = TrueWindKnots;
		WaveParams.FetchMeters = kPolarFetchMeters;
		WaveParams.bCalibrationSea = true;
		Waves.SetWind(WaveParams);
		Waves.SnapToTarget();
		FBoatModel Boat(Config);
		// Beam-on to the wind, knocked flat to leeward (wind from starboard, heeled to port), sheets let go.
		Boat.Reset(0.0, 0.0, -90.0 * kDegToRad, 0.0);
		FBoatControls C;
		C.MainSheet = C.JibSheet = C.SpinSheet = 1.0;
		FBoatState& S = Boat.GetMutableState();
		S.Orientation = S.Orientation * Quat::FromAxisAngle({ 1, 0, 0 }, -StartHeelDeg * kDegToRad);
		for (int I = 0; I < int(Seconds * PhysicsHz); ++I) Boat.Step(PhysicsDt, C, Wind, &Waves);
		return Boat.GetState().Orientation.Tilt() * kRadToDeg; // 0 upright, 90 on her side, 180 turtled
	}

	FCapsizeRun CapsizeAndRight(const FBoatConfig& Config, double TrueWindKnots, double WaitSeconds)
	{
		FWindParams WindParams;
		WindParams.SpeedKnots = TrueWindKnots;
		WindParams.GustIntensity = 0.2;
		const FWindField Wind(WindParams);
		FWaveField Waves(7);
		FWaveParams WaveParams;
		WaveParams.WindSpeedKnots = TrueWindKnots;
		WaveParams.FetchMeters = kPolarFetchMeters;
		WaveParams.bCalibrationSea = true;
		Waves.SetWind(WaveParams);
		Waves.SnapToTarget();
		FBoatModel Boat(Config);
		Boat.Reset(0.0, 0.0, -70.0 * kDegToRad, 2.0);
		FAutopilot Pilot;
		Pilot.TargetTWADeg = 70.0;
		FBoatControls C;
		C.MainSheet = C.JibSheet = 0.0; // cleated hard in, nobody hiking: over she goes
		FCapsizeRun R;
		double CapsizedAt = -1.0;
		for (int I = 0; I < int(120.0 * PhysicsHz); ++I)
		{
			const double T = I * PhysicsDt;
			if (CapsizedAt < 0.0)
			{
				C.Tiller = Pilot.Update(Boat);
				if (Boat.GetTelemetry().bCapsized) { CapsizedAt = T; C.MainSheet = C.JibSheet = 1.0; C.Tiller = 0.0; }
			}
			else if (T >= CapsizedAt + WaitSeconds)
			{
				if (!C.bRighting) R.TiltAfterWaitDeg = Boat.GetState().Orientation.Tilt() * kRadToDeg;
				C.bRighting = true;
				if (Boat.GetState().Orientation.Tilt() < 30.0 * kDegToRad) { R.RightingSeconds = T - CapsizedAt - WaitSeconds; break; }
			}
			Boat.Step(PhysicsDt, C, Wind, &Waves);
		}
		return R;
	}

	FSpeedRun SpeedRun(const FBoatConfig& Config, double TrueWindKnots, double TwaDeg, bool bSpinnaker, double GustIntensity, double FetchMeters, double Seconds, int Reefs)
	{
		const FRunResult R = SteadyRun(Config, TrueWindKnots, TwaDeg, bSpinnaker, Reefs, 30.0, Seconds, GustIntensity, FetchMeters, 3);
		return { R.PeakKnots, R.MeanKnots, R.MaxTiltDeg };
	}

	std::vector<FReferenceCheck> RunReferenceChecks(bool bQuick)
	{
		std::vector<FReferenceCheck> Out;
		const FBoatConfig J22 = FBoatConfig::Make(EBoatType::J22);
		const FBoatConfig C30 = FBoatConfig::Make(EBoatType::Catalina30);

		// Heel, close-hauled with a full crew hiking and trimming as a good crew does.
		for (double Tws : { 6.0, 8.0 })
		{
			const FRunResult R = SteadyRun(J22, Tws, 42.0, false, 0, 30.0, 12.0);
			Out.push_back(Check("Heel", Fmt("J/22 close-hauled, %.0f kn", Tws), R.MeanHeelDeg, 0.0, 7.0, "deg", "North Sails J/22 guide: 3-4 deg in 6-8 kn (tolerance 3 deg)"));
		}
		for (double Tws : { 10.0, 12.0, 14.0 })
		{
			const FRunResult R = SteadyRun(J22, Tws, 42.0, false, 0, 30.0, 12.0);
			Out.push_back(Check("Heel", Fmt("J/22 close-hauled, %.0f kn", Tws), R.MeanHeelDeg, 0.0, 15.0, "deg", "North / Quantum: crew hiking, nearly flat to about 14 kn (under 12, tolerance 3)"));
		}
		const double C30Table[][3] = { { 6.0, 4.0, 0 }, { 10.0, 15.0, 0 }, { 12.0, 17.0, 0 }, { 16.0, 21.0, 0 }, { 20.0, 22.0, 1 } };
		for (const auto& Row : C30Table)
		{
			const FRunResult R = SteadyRun(C30, Row[0], 40.0, false, int(Row[2]), 35.0, 12.0);
			Out.push_back(Check("Heel", Fmt(Row[2] > 0 ? "Catalina 30 close-hauled, %.0f kn, one reef" : "Catalina 30 close-hauled, %.0f kn", Row[0]),
				R.MeanHeelDeg, Row[1] - 3.0, Row[1] + 3.0, "deg", "Catalina 30 owners' heel table (tolerance 3 deg)"));
		}

		// Tacking angles: twice the best-VMG true wind angle (heading to heading).
		{
			const FVmgResult J = BestUpwind(J22, 10.0);
			Out.push_back(Check("Tacking", "J/22 tacking angle, 10 kn", 2.0 * J.TwaDeg, 72.0, 93.0, "deg", "J/22 tacks through 75-90 deg (tolerance 3)"));
			const FVmgResult H = BestUpwind(FBoatConfig::Make(EBoatType::Hobie16), 10.0);
			Out.push_back(Check("Tacking", "Hobie 16 tacking angle, 10 kn", 2.0 * H.TwaDeg, 87.0, 103.0, "deg", "Hobie 16 tacks through 90-100 deg (tolerance 3)"));
			const FVmgResult L = BestUpwind(FBoatConfig::Make(EBoatType::ILCA7), 10.0);
			Out.push_back(Check("Tacking", "ILCA 7 best upwind TWA, 10 kn", L.TwaDeg, 37.0, 49.0, "deg", "ILCA best TWA 40-46 deg (Day 2017 VPP; tolerance 3)"));
		}

		// Roll period at the dock.
		Out.push_back(Check("Roll", "J/22 natural roll period", RollPeriodSeconds(J22), 1.7, 2.3, "s", "IMO A.562 estimate from ORC righting moment: 2.0 s (tolerance 15%)"));

		// Lake waves: 15 kn over 8 miles of fetch on Ray Hubbard (mean depth 6.9 m).
		{
			const double U = 15.0 * kKnot, Fetch = 8.0 * 1609.344;
			Out.push_back(Check("Waves", "Ray Hubbard Hs, 15 kn over 8 mi", FWaveField::TargetSignificantHeight(U, Fetch), 0.36, 0.56, "m", "CEM / SPM-shallow: 0.43-0.47 m (tolerance 20%)"));
			Out.push_back(Check("Waves", "Ray Hubbard peak period, 15 kn over 8 mi", FWaveField::TargetPeakPeriod(U, Fetch), 1.8, 3.1, "s", "CEM / SPM-shallow: 2.2-2.6 s (tolerance 20%)"));
		}

		// Capsize: dinghies and the beach cat stay down until righted; keelboats come back; the big multihulls stay inverted.
		for (EBoatType T : { EBoatType::Sunfish, EBoatType::ILCA7, EBoatType::Hobie16 })
		{
			const FBoatConfig C = FBoatConfig::Make(T);
			Out.push_back(Check("Capsize", std::string(C.Name) + " left alone on her side for 60 s", HeelAfterCapsize(C, 88.0, 12.0, 60.0), 60.0, 180.0, "deg",
				"Capsized dinghies and beach cats lie at about 90 deg (or turtle) until the crew rights them"));
		}
		for (EBoatType T : { EBoatType::Sunfish, EBoatType::ILCA7, EBoatType::Hobie16 })
		{
			const FBoatConfig C = FBoatConfig::Make(T);
			const FCapsizeRun Run = CapsizeAndRight(C, 18.0, 20.0);
			Out.push_back(Check("Capsize", std::string(C.Name) + " 20 s after a capsize in 18 kn", Run.TiltAfterWaitDeg, 60.0, 145.0, "deg",
				"Still on her side, sail on the water (SUN-S-004, SUN-S-006, H16-C-004)"));
			Out.push_back(Check("Capsize", std::string(C.Name) + " righted from her side", Run.RightingSeconds, 3.0, 30.0, "s",
				"Righted in about 10-30 s with the crew on the board or the righting line (SUN-S-004, H16-C-001)"));
		}
		for (EBoatType T : { EBoatType::J22, EBoatType::Catalina22, EBoatType::Catalina30, EBoatType::Maxi })
		{
			const FBoatConfig C = FBoatConfig::Make(T);
			Out.push_back(Check("Capsize", std::string(C.Name) + " knocked down to 85 deg, 30 s later", HeelAfterCapsize(C, 85.0, 12.0, 30.0), 0.0, 35.0, "deg",
				"Ballasted keelboats come back up by themselves"));
		}
		for (EBoatType T : { EBoatType::Corsair880, EBoatType::Lagoon42 })
		{
			const FBoatConfig C = FBoatConfig::Make(T);
			Out.push_back(Check("Capsize", std::string(C.Name) + " inverted, 60 s later", HeelAfterCapsize(C, 178.0, 12.0, 60.0), 150.0, 180.0, "deg",
				"Capsized trimarans and cruising cats stay inverted (crane or salvage)"));
		}

		// Speed ceilings (gusty wind, short lake waves, 3 minutes).
		{
			const FRunResult Steady = SteadyRun(J22, 20.0, 135.0, true, 0, 40.0, 20.0);
			Out.push_back(Check("Top speed", "J/22 spinnaker 135 deg, 20 kn steady", Steady.MeanKnots, 9.40 * 0.92, 9.40 * 1.08, "kn", "ORC J/22 certificate: 9.40 kn (tolerance 8%)"));
			// (Gust intensity 0.10 puts the 99th percentile of the one-second wind at 25 kn on a 20 kn day in W1's field with its
			// kilometre cells; 0.2 took it to 31.)
			const FSpeedRun A = SpeedRun(J22, 20.0, 135.0, true, 0.10, 13000.0, 180.0);
			Out.push_back(Check("Top speed", "J/22 spinnaker run, 20 kn gusting 25: peak", A.PeakKnots, 8.0, 12.0, "kn", "Bursts of about 9-12 kn on waves (J/22 GPS 9.7 kn peak in just under 20 kn; method target)"));
			const FSpeedRun B = SpeedRun(J22, 30.0, 150.0, false, 0.2, 13000.0, 180.0, 1);
			Out.push_back(Check("Top speed", "J/22 running, 30 kn, reefed: peak", B.PeakKnots, 9.0, 16.0, "kn", "Geronimo J/22, 30+ kn: 'around 14 or 15 knots'; 16 kn record"));
			// The ILCA's top speed in a big gust, both ways: a steady 22 kn, and a 16 kn day gusting to about 22 in W1's puffs.
			// The sailor (auto-trim) dumps the sheet in the hand, sheets in against a roll to windward and sits back on the
			// plane, and must stay upright for the whole three minutes (a capsized run's peak means nothing).
			// The prologue maxi in the mistral: two reefs and the J4, a broad reach in 30 kn gusting 37 (gust intensity 0.10; her own reefed gale
			// sails; no spinnaker), upright throughout.
			const FSpeedRun M = SpeedRun(FBoatConfig::Make(EBoatType::Maxi), 30.0, 120.0, false, 0.10, 13000.0, 120.0, 2);
			Out.push_back(Check("Top speed", "Maxi 100 broad reach, 30 kn, two reefs: peak", M.PeakKnots, 18.0, 34.0, "kn",
				"100 ft maxis reach in the 20s in a gale, one-second peaks into the low 30s (Comanche's 24 h record averaged 25.8 kn; method target)"));
			Out.push_back(Check("Capsize", "Maxi 100 broad reach, 30 kn, two reefs: most tilt", M.MaxTiltDeg, 0.0, 60.0, "deg",
				"A ballasted maxi stays on her feet reefed in a gale"));
			const FBoatConfig Ilca = FBoatConfig::Make(EBoatType::ILCA7);
			const FSpeedRun L = SpeedRun(Ilca, 22.0, 110.0, false, 0.0, 13000.0, 180.0);
			// Up to 18 since she surfs (docs/wave-physics/): the class's GPS logs reach 21.6 kn running in a 40 kn gust on
			// flat water and 22.2 kn reaching (ilcasailing.org, "Australian speed rivalry"); 22 kn of wind with the lake's
			// chop to ride sits between.
			Out.push_back(Check("Top speed", "ILCA 7 broad reach, 22 kn: peak", L.PeakKnots, 10.0, 18.0, "kn", "ILCA about 15 kn GPS in a big gust; class GPS logs to 21.6-22.2 kn in 40 kn"));
			Out.push_back(Check("Top speed", "ILCA 7 broad reach, 22 kn: heel at most", L.MaxTiltDeg, 0.0, 70.0, "deg", "A good sailor keeps her up on a heavy-air reach (past 70 deg the model counts a capsize)"));
			// (Gust intensity 0.14 puts the 99th percentile of the one-second wind at 22 kn on a 16 kn day; 0.25 took it to 27.)
			const FSpeedRun G = SpeedRun(Ilca, 16.0, 110.0, false, 0.14, 13000.0, 180.0);
			Out.push_back(Check("Top speed", "ILCA 7 broad reach, 16 kn gusting 22: peak", G.PeakKnots, 10.0, 18.0, "kn", "ILCA about 15 kn GPS in a big gust; class GPS logs to 21.6-22.2 kn in 40 kn"));
			Out.push_back(Check("Top speed", "ILCA 7 broad reach, 16 kn gusting 22: heel at most", G.MaxTiltDeg, 0.0, 70.0, "deg", "A good sailor keeps her up on a heavy-air reach (past 70 deg the model counts a capsize)"));
		}

		// Portsmouth: lap time on a windward-leeward course relative to the ILCA, by wind band (US Sailing D-PN, no spinnakers).
		struct FDpn { EBoatType Type; double Band[3]; };
		const FDpn Fleet[] = {
			{ EBoatType::Sunfish, { 100.4, 97.8, 95.8 } },
			{ EBoatType::Catalina22, { 96.3, 95.3, 95.1 } },
			{ EBoatType::Catalina30, { 87.1, 85.5, 82.7 } },
			{ EBoatType::Hobie16, { 78.7, 74.1, 71.3 } },
		};
		const double IlcaDpn[3] = { 92.3, 91.0, 88.2 };
		const double BandWind[3] = { 6.0, 10.0, 15.0 };
		const char* BandName[3] = { "DPN2 4-7 kn", "DPN3 8-11 kn", "DPN4 12+ kn" };
		const FBoatConfig Ilca = FBoatConfig::Make(EBoatType::ILCA7);
		for (int B = bQuick ? 1 : 0; B < 3; ++B)
		{
			auto Lap = [&](const FBoatConfig& C) { return 1.0 / BestUpwind(C, BandWind[B]).VmgKnots + 1.0 / BestDownwind(C, BandWind[B]).VmgKnots; };
			const double IlcaLap = Lap(Ilca);
			for (const FDpn& D : Fleet)
			{
				const FBoatConfig C = FBoatConfig::Make(D.Type);
				const double Ratio = Lap(C) / IlcaLap;
				const double Target = D.Band[B] / IlcaDpn[B];
				Out.push_back(Check("Portsmouth", std::string(C.Name) + " lap time / ILCA, " + BandName[B], Ratio, Target * 0.92, Target * 1.08, "ratio",
					"US Sailing 2017 D-PN by wind band (tolerance 8%)"));
			}
		}
		return Out;
	}
}
