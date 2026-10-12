#include "Scenarios.h"
#include "FixedStepper.h"

namespace Sailing
{
	FTackResult RunTack(double TrueWindKnots, double CloseHauledTWADeg, double TackTiller)
	{
		FWindParams WindParams;
		WindParams.SpeedKnots = TrueWindKnots;
		const FWindField Wind(WindParams);
		FWaveField Waves(7);
		FWaveParams WaveParams;
		WaveParams.WindSpeedKnots = TrueWindKnots;
		WaveParams.FetchMeters = kPolarFetchMeters;
		Waves.SetWind(WaveParams);
		Waves.SnapToTarget();

		FBoatModel Boat;
		Boat.Reset(0.0, 0.0, -CloseHauledTWADeg * kDegToRad, 0.7 * TrueWindKnots * kKnot);
		FAutopilot Pilot;
		Pilot.TargetTWADeg = CloseHauledTWADeg;
		FAutoTrim Trim;
		FBoatControls Controls;
		Controls.MainSheet = Controls.JibSheet = 0.15;

		auto Run = [&](double Seconds, auto&& PerStep)
		{
			for (int I = 0; I < int(Seconds * PhysicsHz); ++I)
			{
				Controls = Trim.Update(Boat, Controls, PhysicsDt);
				Controls.Tiller = Pilot.Update(Boat);
				Boat.Step(PhysicsDt, Controls, Wind, &Waves);
				PerStep();
			}
		};

		FTackResult R;
		Run(40.0, [] {});
		R.SpeedBeforeKnots = Boat.GetTelemetry().BoatSpeed / kKnot;
		R.MinSpeedKnots = R.SpeedBeforeKnots;

		// Helm over firmly (about 24 degrees of rudder) and steer for the same angle on port tack.
		Pilot.TargetTWADeg = -CloseHauledTWADeg;
		Pilot.MaxTiller = TackTiller;
		Pilot.bKeepShortOfStall = false;
		const double Start = Boat.GetState().Time;
		Run(25.0, [&]
		{
			const FBoatTelemetry& T = Boat.GetTelemetry();
			R.MinSpeedKnots = std::min(R.MinSpeedKnots, T.BoatSpeed / kKnot);
			// Settled: within 5 degrees of the new close-hauled angle.
			if (!R.bCompleted && T.TrueWindAngle < 0.0 && std::fabs(T.TrueWindAngle * kRadToDeg + CloseHauledTWADeg) < 5.0)
			{
				R.bCompleted = true;
				R.TackSeconds = Boat.GetState().Time - Start;
			}
			if (std::fabs(Boat.GetState().Time - Start - 10.0) < 0.5 * PhysicsDt)
			{
				R.SpeedAfter10sKnots = T.BoatSpeed / kKnot;
			}
		});
		return R;
	}

	FIronsResult RunIrons(double TrueWindKnots, double Seconds, double TillerInput)
	{
		FWindParams WindParams;
		WindParams.SpeedKnots = TrueWindKnots;
		const FWindField Wind(WindParams);

		FBoatModel Boat;
		Boat.Reset(0.0, 0.0, 0.0, 0.0); // bow straight into the wind (wind from +X)
		FBoatControls Controls;
		Controls.MainSheet = 0.5;
		Controls.JibSheet = 0.5;
		Controls.Tiller = TillerInput;

		FIronsResult R;
		for (int I = 0; I < int(Seconds * PhysicsHz); ++I)
		{
			Boat.Step(PhysicsDt, Controls, Wind);
			R.MaxForwardSpeedKnots = std::max(R.MaxForwardSpeedKnots, Boat.GetTelemetry().ForwardSpeed / kKnot);
		}
		const FBoatTelemetry& T = Boat.GetTelemetry();
		R.FinalTWADeg = T.TrueWindAngle * kRadToDeg;
		R.FinalForwardSpeedKnots = T.ForwardSpeed / kKnot;
		R.bInIronsAtEnd = T.bInIrons;
		return R;
	}
}
