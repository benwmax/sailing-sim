#include "EasyAssists.h"
#include "FixedStepper.h"
#include "PolarReference.h"

namespace Sailing
{
	FEasyAssists FEasyAssists::For(const FBoatConfig& Config, bool bOn)
	{
		(void)Config; // one set for the fleet so far: the per-boat numbers scale from the config (HeelCapDegFor, ApplyTo)
		FEasyAssists A;
		A.bEnabled = bOn;
		return A;
	}

	double FEasyAssists::HeelCapDegFor(const FBoatConfig& Config) const
	{
		return bEnabled ? std::min(HeelCapPerTrimLimit * Config.TrimHeelLimitDeg, HeelCapMaxDeg) : 0.0;
	}

	void FEasyAssists::ApplyTo(FBoatConfig& Config, double TotalMassKg) const
	{
		const FBoatConfig Own = FBoatConfig::Make(Config.Type);
		Config.HelmStiffness = bEnabled ? HelmStiffness : Own.HelmStiffness;
		Config.ExtraRollDamping = bEnabled ? RollDampingPerTonne * TotalMassKg / 1000.0 : Own.ExtraRollDamping;
		Config.HeelYawCoef = bEnabled ? HeelYawScale * Own.HeelYawCoef : Own.HeelYawCoef;
		Config.YawDampingLinear = bEnabled ? YawDampingScale * Own.YawDampingLinear : Own.YawDampingLinear;
		Config.HeelCapDeg = HeelCapDegFor(Own);
		Config.HeelCapSoftDeg = bEnabled ? HeelCapSoftDeg : Own.HeelCapSoftDeg;
		Config.HeelCapLeverM = bEnabled ? CapLeverM : Own.HeelCapLeverM;
	}

	void FEasyAssists::ApplyTo(FAutoTrimSettings& Settings) const
	{
		const FAutoTrimSettings Own;
		Settings.RateScale = bEnabled ? TrimRateScale : Own.RateScale;
		Settings.HeelLimitDeg = bEnabled ? TrimHeelScale * Own.HeelLimitDeg : Own.HeelLimitDeg;
		Settings.bEasePuffs = bEnabled ? bEasePuffs : Own.bEasePuffs;
	}

	ENoGoCue NoGoCueFor(const FBoatTelemetry& T, const FEasyAssists& Assists)
	{
		const double Twa = std::fabs(T.TrueWindAngle) * kRadToDeg;
		if (T.bInIrons || Twa < Assists.NoGoDeg()) return ENoGoCue::Inside;
		return Twa < Assists.NoGoWarnDeg() ? ENoGoCue::Near : ENoGoCue::Clear;
	}

	FBoatControls FEasyHelm::Update(const FBoatModel& Boat, const FBoatControls& Controls, const FEasyAssists& Assists, double Dt)
	{
		FBoatControls Out = Controls;
		if (!Assists.bEnabled)
		{
			Reset();
			return Out;
		}
		const FBoatTelemetry& T = Boat.GetTelemetry();
		const double Twa = T.TrueWindAngle * kRadToDeg;
		const bool bStuck = std::fabs(Twa) < Assists.NoGoCueDeg && T.ForwardSpeed < Assists.StuckKnots * kKnot;
		if (Side == 0)
		{
			StuckTime = bStuck ? StuckTime + Dt : 0.0;
			// Fall off onto the tack she is nearer (past head to wind mid-tack, that is the new one), as the jib feels it:
			// the apparent wind picks the side FBoatModel backs it on, and a jib backed on the other side would push the
			// bow the wrong way.
			if (StuckTime > Assists.IronsHelpSeconds) Side = T.ApparentWindAngle >= 0.0 ? 1 : -1;
		}
		else if (Twa * Side > Assists.RecoveredTWADeg || Twa * Side < -FEasyAssists::kRealisticNoGoDeg)
		{
			Reset(); // off the wind: the player and the trim have her again (or a shift put her on the other tack)
		}
		if (Side == 0)
		{
			// The bear-away guard: the tiller let go (or near it) inside the no-go cue while she still has way on, the crew
			// bears her off to the cue's edge on the tack she is on, in proportion to how far inside she is.
			const double Inside = Assists.NoGoCueDeg - std::fabs(Twa);
			if (Inside > 0.0 && std::fabs(Controls.Tiller) < Assists.GuardDeadband && T.ForwardSpeed > Assists.StuckKnots * kKnot)
			{
				const double Nudge = std::min(Inside / Assists.NoGoCueDeg * 2.0, 1.0) * Assists.GuardTiller;
				Out.Tiller = Controls.Tiller - (Twa >= 0.0 ? 1.0 : -1.0) * Nudge;
			}
			return Out;
		}
		// Once the jib is backed the sheet holds it on its side (BoatModel chose it from the jib's own wind, which head to
		// wind can differ from the masthead's): steer for the tack it pushes her onto.
		if (Boat.GetState().BackedJibSide != 0) Side = Boat.GetState().BackedJibSide;
		// To bring the wind further onto the Side tack the bow turns away from it: to port on starboard tack. A tiller
		// turns the bow the other way while she makes sternway.
		const double Ahead = T.ForwardSpeed >= 0.0 ? 1.0 : -1.0;
		Out.Tiller = -Side * Ahead * Assists.RecoveryTiller;
		Out.bBackJib = true;   // held to windward, it pushes the bow off (BoatModel picks the side from the jib's wind)
		Out.JibSheet = Assists.RecoveryJibSheet;
		Out.MainSheet = 1.0;   // the main let run so it does not drive her back up
		return Out;
	}

	namespace
	{
		struct FEasyRig
		{
			FBoatModel Boat;
			FAutoTrim Trim;
			FEasyHelm Helm;
			FEasyAssists Assists;
			FBoatControls Controls;
			FEasyRig(EBoatType Type, bool bEasy) : Boat(FBoatConfig::Make(Type))
			{
				Assists = FEasyAssists::For(Boat.GetConfig(), bEasy);
				Assists.ApplyTo(Boat.GetMutableConfig(), Boat.TotalMass());
				Assists.ApplyTo(Trim.Settings);
			}
			/** One step as the game runs it: the trim assist (the player's tiller kept), Easy's helm on a copy, the boat. */
			void Step(const FWindField& Wind, const FWaveField* Waves, double PlayerTiller)
			{
				Controls = Trim.Update(Boat, Controls, PhysicsDt);
				Controls.Tiller = PlayerTiller;
				Boat.Step(PhysicsDt, Helm.Update(Boat, Controls, Assists, PhysicsDt), Wind, Waves);
			}
		};

		void SetCalibrationSea(FWaveField& Waves, double Knots)
		{
			FWaveParams P;
			P.WindSpeedKnots = Knots;
			P.FetchMeters = kPolarFetchMeters;
			P.bCalibrationSea = true;
			Waves.SetWind(P);
			Waves.SnapToTarget();
		}

		double LeewardHeelDeg(const FBoatModel& Boat)
		{
			return Boat.GetTelemetry().Heel * Boat.GetState().WindwardSide * kRadToDeg;
		}
	}

	FEasyReachResult RunEasyReach(EBoatType Type, bool bEasy, double TrueWindKnots, double TwaDeg, double Seconds, double GustIntensity)
	{
		FWindParams WP;
		WP.SpeedKnots = TrueWindKnots;
		WP.GustIntensity = GustIntensity;
		WP.Seed = 22;
		const FWindField Wind(WP);
		FWaveField Waves(7);
		SetCalibrationSea(Waves, TrueWindKnots);
		FEasyRig R(Type, bEasy);
		R.Boat.Reset(0.0, 0.0, -TwaDeg * kDegToRad, 0.5 * TrueWindKnots * kKnot);
		FAutopilot Pilot;
		Pilot.TargetTWADeg = TwaDeg;
		FEasyReachResult Out;
		Out.HeelCapDeg = R.Assists.HeelCapDegFor(R.Boat.GetConfig());
		double SpeedSum = 0.0;
		int SpeedN = 0;
		const double Course = -TwaDeg * kDegToRad; // the TWA in the mean wind (from 0)
		for (int I = 0; I < int(Seconds * PhysicsHz); ++I)
		{
			// A helm on a reach steers a compass course: the pilot's error is the heading's off the course, not the TWA's.
			const FBoatTelemetry& Now = R.Boat.GetTelemetry();
			Pilot.TargetTWADeg = (Now.TrueWindAngle - WrapAngle(Course - Now.Heading)) * kRadToDeg;
			R.Step(Wind, &Waves, Pilot.Update(R.Boat));
			const FBoatTelemetry& T = R.Boat.GetTelemetry();
			Out.MaxHeelDeg = std::max(Out.MaxHeelDeg, LeewardHeelDeg(R.Boat));
			Out.bCapsized |= T.bCapsized;
			if (R.Boat.GetState().Time > 20.0)
			{
				// The course is the TWA held in the mean wind (from 0): a gust's shift moves the TWA but not the course.
				Out.MaxCourseErrorDeg = std::max(Out.MaxCourseErrorDeg, std::fabs(WrapAngle(T.Heading - Course)) * kRadToDeg);
				SpeedSum += T.BoatSpeed / kKnot;
				++SpeedN;
			}
		}
		Out.MeanSpeedKnots = SpeedN ? SpeedSum / SpeedN : 0.0;
		return Out;
	}

	FEasyIronsResult RunEasyIrons(EBoatType Type, bool bEasy, double TrueWindKnots, double Seconds)
	{
		FWindParams WP;
		WP.SpeedKnots = TrueWindKnots;
		const FWindField Wind(WP);
		FEasyRig R(Type, bEasy);
		R.Boat.Reset(0.0, 0.0, 0.0, 0.0); // bow straight into the wind (from +X)
		R.Controls.MainSheet = R.Controls.JibSheet = 0.5;
		FEasyIronsResult Out;
		for (int I = 0; I < int(Seconds * PhysicsHz); ++I)
		{
			// Realistic leaves the sheets where they are (a beginner who has not found them); Easy's trim is always on.
			if (bEasy) R.Step(Wind, nullptr, 0.0);
			else R.Boat.Step(PhysicsDt, R.Controls, Wind);
			const FBoatTelemetry& T = R.Boat.GetTelemetry();
			if (Out.FilledSeconds < 0.0 && std::fabs(T.TrueWindAngle) * kRadToDeg > 50.0 && T.ForwardSpeed > 1.5 * kKnot)
			{
				Out.FilledSeconds = R.Boat.GetState().Time;
			}
		}
		Out.FinalTwaDeg = R.Boat.GetTelemetry().TrueWindAngle * kRadToDeg;
		Out.FinalSpeedKnots = R.Boat.GetTelemetry().ForwardSpeed / kKnot;
		return Out;
	}

	FEasyTackResult RunEasyTack(EBoatType Type, bool bEasy, double TrueWindKnots, double HoldSeconds)
	{
		FWindParams WP;
		WP.SpeedKnots = TrueWindKnots;
		const FWindField Wind(WP);
		FWaveField Waves(7);
		SetCalibrationSea(Waves, TrueWindKnots);
		FEasyRig R(Type, bEasy);
		constexpr double CloseHauled = 45.0;
		R.Boat.Reset(0.0, 0.0, -CloseHauled * kDegToRad, 0.5 * TrueWindKnots * kKnot);
		R.Controls.MainSheet = R.Controls.JibSheet = 0.15;
		FAutopilot Pilot;
		Pilot.TargetTWADeg = CloseHauled;
		for (int I = 0; I < int(30.0 * PhysicsHz); ++I) R.Step(Wind, &Waves, Pilot.Update(R.Boat));
		// Starboard tack (wind from starboard): the bow turns to starboard, through the wind (tiller +1).
		FEasyTackResult Out;
		const double Start = R.Boat.GetState().Time;
		for (int I = 0; I < int(30.0 * PhysicsHz); ++I)
		{
			R.Step(Wind, &Waves, R.Boat.GetState().Time - Start < HoldSeconds ? 1.0 : 0.0);
			Out.MaxHeelDeg = std::max(Out.MaxHeelDeg, std::fabs(R.Boat.GetTelemetry().Heel) * kRadToDeg);
		}
		const FBoatTelemetry& T = R.Boat.GetTelemetry();
		Out.FinalTwaDeg = T.TrueWindAngle * kRadToDeg;
		Out.FinalSpeedKnots = T.ForwardSpeed / kKnot;
		Out.bTacked = Out.FinalTwaDeg < -FEasyAssists::kRealisticNoGoDeg && Out.FinalSpeedKnots > 1.5;
		return Out;
	}
}
