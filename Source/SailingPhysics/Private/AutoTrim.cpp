#include "AutoTrim.h"

namespace Sailing
{
	FBoatControls FAutoTrim::Update(const FBoatModel& Boat, const FBoatControls& Current, double Dt)
	{
		const FBoatTelemetry& T = Boat.GetTelemetry();
		const FBoatState& S = Boat.GetState();
		FBoatControls Out = Current;
		const FAutoTrimSettings& Set = Settings;

		// Angle each sail's foot should sit at: apparent wind angle minus twist minus the target angle of attack, averaged over strips.
		auto FootAngleFor = [&](const FSailStripState* Strips, int N, double FootAngleNow)
		{
			double Sum = 0.0;
			for (int I = 0; I < N; ++I)
			{
				const FSailStripState& St = Strips[I];
				const double Target = St.StallAlpha - Set.AlphaMarginDeg * kDegToRad;
				// Current alpha at this strip, and how much the foot must move to reach the target there.
				Sum += (St.AlphaN - Target);
			}
			return FootAngleNow + Sum / N;
		};

		// Heel toward leeward is positive here; heeled to windward is negative.
		const double Heel = T.Heel * S.WindwardSide * kRadToDeg;
		const double Excess = Heel - Set.HeelLimitDeg;
		MainEase = Clamp(MainEase + (Excess > 0.0 ? Excess * 0.6 : -2.0) * kDegToRad * Dt, 0.0, 25.0 * kDegToRad);

		const double TwsKnots = T.TrueWindSpeed / kKnot;
		const double Flatten = Clamp((TwsKnots - Set.FlattenFromKnots) / Set.FlattenRangeKnots, 0.0, 1.0);
		const double Twa = std::fabs(T.TrueWindAngle) * kRadToDeg;
		const double Downwind = SmoothStep(100.0, 140.0, Twa);
		const double Reach = SmoothStep(55.0, 85.0, Twa);

		const double Rate = 0.8 * Dt; // sheets move at most 0.8 of full travel per second
		if (Set.bTrimMain && T.NumMainStrips > 0)
		{
			const double Foot = FootAngleFor(T.MainStrips, T.NumMainStrips, S.BoomAngle * S.MainSide) + MainEase;
			// Traveler carries the boom toward the centerline upwind; the sheet does the rest.
			const double Traveler = Clamp(Foot / (8.0 * kDegToRad), -1.0, 0.0) + Clamp(MainEase / (8.0 * kDegToRad), 0.0, 1.0);
			const double Sheet = Clamp((Foot - Clamp(Traveler, -1.0, 1.0) * 8.0 * kDegToRad) / (85.0 * kDegToRad), 0.0, 1.0);
			Out.Traveler = MoveToward(Current.Traveler, Clamp(Traveler, -1.0, 1.0), Rate * 2.0);
			Out.MainSheet = MoveToward(Current.MainSheet, Sheet, Rate);
		}
		if (Set.bTrimJib && T.NumJibStrips > 0)
		{
			const double Foot = FootAngleFor(T.JibStrips, T.NumJibStrips, S.JibAngle * S.JibSide);
			Out.JibSheet = MoveToward(Current.JibSheet, Clamp((Foot - 8.0 * kDegToRad) / (72.0 * kDegToRad), 0.0, 1.0), Rate);
		}
		Out.bWingOnWing = Twa > 155.0;
		if (Set.bShape)
		{
			Out.Backstay = MoveToward(Current.Backstay, Flatten * (1.0 - Downwind), Rate);
			Out.Cunningham = MoveToward(Current.Cunningham, Flatten * (1.0 - Downwind), Rate);
			Out.Outhaul = MoveToward(Current.Outhaul, Lerp(0.3 + 0.7 * Flatten, 0.1, Downwind), Rate);
			Out.Vang = MoveToward(Current.Vang, Lerp(std::max(0.2 + 0.7 * Flatten, 0.65 * Reach), 0.5, Downwind), Rate);
		}
		if (Set.bHike)
		{
			// Hike out as the boat heels; in light air or running, move in (or to leeward) to keep a little leeward heel.
			Out.Hike = Clamp(Current.Hike + Clamp((Heel - 4.0) / 4.0, -1.0, 1.0) * 0.8 * Dt, -1.0, 1.0);
		}
		return Out;
	}

	double FAutopilot::Update(const FBoatModel& Boat) const
	{
		const FBoatTelemetry& T = Boat.GetTelemetry();
		// Heading error: to raise the TWA on starboard tack (wind from +Y side), turn the bow away (to port).
		const double Error = WrapAngle(T.TrueWindAngle - TargetTWADeg * kDegToRad);
		const double YawRate = Boat.GetState().AngularVelocity.Z;
		return Clamp(Gain * Error - RateGain * YawRate, -MaxTiller, MaxTiller);
	}
}
