#include "PolarReference.h"
#include "FixedStepper.h"

namespace Sailing
{
	const std::vector<FPolarPoint>& J22ReferencePolar()
	{
		static const char* Orc = "ORC";
		static const char* Beat = "ORC beat VMG / cos(beat angle)";
		static const char* Interp = "ORC, 15 kn interpolated 14-20";
		static const char* NonSpin6 = "approx. non-spinnaker: ORC x 0.84";
		static const char* NonSpin = "approx. non-spinnaker: ORC x 0.89";
		static const char* NonSpinInterp = "approx. non-spinnaker: ORC x 0.91, 15 kn interpolated";
		static const std::vector<FPolarPoint> Polar = {
			{ 6, 43.5, 2.85 / std::cos(43.5 * kDegToRad), Beat },
			{ 6, 52, 4.3, Orc }, { 6, 60, 4.6, Orc }, { 6, 75, 4.7, Orc }, { 6, 90, 4.9, Orc },
			{ 6, 110, 4.9 * 0.84, NonSpin6 }, { 6, 120, 4.7 * 0.84, NonSpin6 }, { 6, 135, 4.2 * 0.84, NonSpin6 },
			{ 6, 150, 3.6 * 0.84, NonSpin6 }, { 6, 172, 3.1 / std::cos(8.0 * kDegToRad) * 0.84, NonSpin6 },

			{ 10, 40.9, 3.87 / std::cos(40.9 * kDegToRad), Beat },
			{ 10, 52, 5.6, Orc }, { 10, 60, 5.8, Orc }, { 10, 75, 5.9, Orc }, { 10, 90, 6.1, Orc },
			{ 10, 110, 6.2 * 0.89, NonSpin }, { 10, 120, 6.1 * 0.89, NonSpin }, { 10, 135, 5.9 * 0.89, NonSpin },
			{ 10, 150, 5.4 * 0.89, NonSpin }, { 10, 172, 4.7 / std::cos(8.0 * kDegToRad) * 0.89, NonSpin },

			{ 15, 38.6, 4.20 / std::cos(38.6 * kDegToRad), Beat },
			{ 15, 52, 6.0 + 0.2 / 6, Interp }, { 15, 60, 6.2 + 0.2 / 6, Interp }, { 15, 75, 6.5 + 0.4 / 6, Interp },
			{ 15, 90, 6.6 + 0.9 / 6, Interp },
			{ 15, 110, (7.2 + 1.1 / 6) * 0.91, NonSpinInterp }, { 15, 120, (7.2 + 2.0 / 6) * 0.91, NonSpinInterp },
			{ 15, 135, (6.8 + 2.4 / 6) * 0.91, NonSpinInterp }, { 15, 150, (6.4 + 1.7 / 6) * 0.91, NonSpinInterp },
			{ 15, 172, (5.8 + 1.3 / 6) / std::cos(8.0 * kDegToRad) * 0.91, NonSpinInterp },
		};
		return Polar;
	}

	FSteadyResult SailSteadyWith(double TrueWindKnots, double TrueWindAngleDeg, const FAutoTrimSettings& Trim, const FBoatConfig& Config, double SettleSeconds, double AverageSeconds, bool bSpinnaker)
	{
		FWindParams WindParams;
		WindParams.SpeedKnots = TrueWindKnots;
		WindParams.FromDegrees = 0.0; // wind from +X; heading chosen to give the TWA
		const FWindField Wind(WindParams);
		FWaveField Waves(7);
		FWaveParams WaveParams;
		WaveParams.WindSpeedKnots = TrueWindKnots;
		WaveParams.WindFromDegrees = WindParams.FromDegrees;
		WaveParams.FetchMeters = kPolarFetchMeters;
		WaveParams.bCalibrationSea = true;
		Waves.SetWind(WaveParams);
		Waves.SnapToTarget();

		FBoatModel Boat(Config);
		const double Heading = -TrueWindAngleDeg * kDegToRad; // TWA = windFrom - heading
		Boat.Reset(0.0, 0.0, Heading, 0.6 * TrueWindKnots * kKnot);
		// Start with the crew already on the windward side, as they would be on a steady course.
		const int Windward = TrueWindAngleDeg >= 0.0 ? 1 : -1;
		Boat.GetMutableState().WindwardSide = Windward;
		Boat.GetMutableState().CrewOffset = Windward * Config.CrewSitOut;

		FAutopilot Pilot;
		Pilot.TargetTWADeg = TrueWindAngleDeg;
		FAutoTrim AutoTrim;
		AutoTrim.Settings = Trim;
		FBoatControls Controls;
		Controls.MainSheet = Clamp(TrueWindAngleDeg / 180.0, 0.0, 1.0);
		Controls.JibSheet = Controls.MainSheet;
		Controls.bSpinnaker = bSpinnaker && Config.HasSpinnaker();
		// Already hiking in a breeze when reaching or beating; sitting in, ready to move, running.
		Controls.Hike = Clamp((TrueWindKnots - 6.0) / 6.0, 0.0, 1.0) * (1.0 - SmoothStep(95.0, 115.0, std::fabs(TrueWindAngleDeg)));
		Controls.SpinSheet = 0.5;

		const int SettleSteps = int(SettleSeconds * PhysicsHz);
		const int AverageSteps = int(AverageSeconds * PhysicsHz);
		FSteadyResult R;
		R.Trim = Trim;
		double SumSq = 0.0;
		for (int I = 0; I < SettleSteps + AverageSteps; ++I)
		{
			Controls = AutoTrim.Update(Boat, Controls, PhysicsDt);
			Controls.Tiller = Pilot.Update(Boat);
			Boat.Step(PhysicsDt, Controls, Wind, &Waves);
			if (I >= SettleSteps)
			{
				const FBoatTelemetry& T = Boat.GetTelemetry();
				const double Speed = T.BoatSpeed / kKnot;
				R.BoatSpeedKnots += Speed;
				SumSq += Speed * Speed;
				R.HeelDeg += std::fabs(T.Heel) * kRadToDeg;
				R.LeewayDeg += std::fabs(T.Leeway) * kRadToDeg;
				R.RudderDeg += -T.RudderAngle * kRadToDeg * (T.TrueWindAngle > 0.0 ? 1.0 : -1.0); // + = weather helm
				R.HelmForceN += T.HelmForce;
				R.TrueWindAngleDeg += T.TrueWindAngle * kRadToDeg;
			}
		}
		const double N = AverageSteps;
		R.BoatSpeedKnots /= N;
		R.SpeedStdDev = std::sqrt(std::max(0.0, SumSq / N - R.BoatSpeedKnots * R.BoatSpeedKnots));
		R.HeelDeg /= N;
		R.LeewayDeg /= N;
		R.RudderDeg /= N;
		R.HelmForceN /= N;
		R.TrueWindAngleDeg /= N;
		return R;
	}

	FSteadyResult SailSteady(double TrueWindKnots, double TrueWindAngleDeg, const FBoatConfig& Config, bool bSearchTrim, bool bSpinnaker)
	{
		// The reference polar is a VPP's: perfect trim, every step (docs/trimmer-hands/). The crews and AI boats in the game
		// sail with human hands (FAutoTrimSettings::bHands); TrimmerHands measures what that costs.
		FAutoTrimSettings Base;
		Base.bHands = false;
		if (!bSearchTrim)
		{
			return SailSteadyWith(TrueWindKnots, TrueWindAngleDeg, Base, Config, 40.0, 15.0, bSpinnaker);
		}
		FSteadyResult Best;
		for (double Margin : { 0.0, 2.0, 4.0 })
		{
			for (double HeelLimit : { 18.0, 25.0 })
			{
				FAutoTrimSettings Trim = Base;
				Trim.AlphaMarginDeg = Margin;
				Trim.HeelLimitDeg = HeelLimit;
				const FSteadyResult R = SailSteadyWith(TrueWindKnots, TrueWindAngleDeg, Trim, Config, 40.0, 15.0, bSpinnaker);
				if (R.BoatSpeedKnots > Best.BoatSpeedKnots)
				{
					Best = R;
				}
			}
		}
		return Best;
	}
}
