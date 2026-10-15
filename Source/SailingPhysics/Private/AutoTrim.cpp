#include "AutoTrim.h"

namespace Sailing
{
	FBoatControls FAutoTrim::Update(const FBoatModel& Boat, const FBoatControls& Current, double Dt)
	{
		const FBoatTelemetry& T = Boat.GetTelemetry();
		const FBoatState& S = Boat.GetState();
		FBoatControls Out = Current;
		const FBoatConfig& Cfg = Boat.GetConfig();
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
		// Heel rate toward leeward (deg/s): a good crew reacts to the boat starting to roll, not only to where it is.
		const double HeelRate = S.AngularVelocity.X * S.WindwardSide * kRadToDeg;
		// The settings' heel limit is for a keelboat that likes 22 degrees; boats that sail flatter scale it down.
		const double Excess = Heel + 0.3 * HeelRate - Set.HeelLimitDeg * Cfg.TrimHeelLimitDeg / 22.0;
		const double EaseRate = 0.6 * std::sqrt(22.0 / Cfg.TrimHeelLimitDeg);
		// Ease as the boat heels past the limit; trim back in slowly, or at once if it starts to heel to windward.
		// (A dinghy sailor, dumping the sheet in the hand as she heels, keeps less of it out afterwards.)
		const double Recover = (Heel < 0.0 ? std::min(-2.0, Heel * 3.0) : -2.0) * (Cfg.DinghyEasePerHeelDeg > 0.0 ? 4.0 : 1.0);
		MainEase = Clamp(MainEase + (Excess > 0.0 ? Excess * EaseRate : Recover) * kDegToRad * Dt, 0.0, Cfg.TrimMaxEaseDeg * kDegToRad);

		const double TwsKnots = T.TrueWindSpeed / kKnot;
		const double Flatten = Clamp((TwsKnots - Set.FlattenFromKnots) / Set.FlattenRangeKnots, 0.0, 1.0);
		const double Twa = std::fabs(T.TrueWindAngle) * kRadToDeg;
		const double Downwind = SmoothStep(100.0, 140.0, Twa);
		const double Reach = SmoothStep(55.0, 85.0, Twa);

		const double Rate = 0.8 * Dt; // sheets move at most 0.8 of full travel per second
		// A dinghy sailor sails her flat with the sheet in the hand: dumps it as soon as she heels past the limit (or starts
		// to roll toward it), and never trims in while she is still overpowered, even if the apparent wind comes forward.
		const bool bDinghy = Cfg.DinghyEasePerHeelDeg > 0.0;
		// Rolling to windward (a death roll starts so on a reach or a run) the sailor sheets in hard instead: it loads the
		// sail to leeward again.
		const double Windward = bDinghy ? std::max(-(Heel + 0.3 * HeelRate) - 3.0, 0.0) : 0.0;
		const double Dump = bDinghy ? (std::max(Excess, 0.0) - Windward) * Cfg.DinghyEasePerHeelDeg * kDegToRad : 0.0;
		const bool bOverpowered = bDinghy && Excess > -3.0;
		// After a dump she trims back on smoothly, not in step with the roll (sheet and body pumping together rock her over).
		constexpr double TrimInRate = 0.25;
		if (Set.bTrimMain && T.NumMainStrips > 0)
		{
			const double Foot = FootAngleFor(T.MainStrips, T.NumMainStrips, S.BoomAngle * S.MainSide) + MainEase + Dump;
			// Traveler carries the boom toward the centerline upwind; the sheet does the rest.
			const double Range = Cfg.TravelerRangeDeg * kDegToRad;
			const double Traveler = Clamp(Foot / Range, -1.0, 0.0) + Clamp(MainEase / Range, 0.0, 1.0);
			const double Sheet = Clamp((Foot - Clamp(Traveler, -1.0, 1.0) * Range) / (Cfg.MainMaxEaseDeg * kDegToRad), 0.0, 1.0);
			Out.Traveler = MoveToward(Current.Traveler, Clamp(Traveler, -1.0, 1.0), Rate * 2.0);
			if (Windward > 0.0) Out.MainSheet = MoveToward(Current.MainSheet, std::min(Sheet, Current.MainSheet), Cfg.DinghySheetRate * Dt);
			else if (bOverpowered) Out.MainSheet = MoveToward(Current.MainSheet, std::max(Sheet, Current.MainSheet), Cfg.DinghySheetRate * Dt);
			else if (bDinghy && MainEase > kDegToRad) Out.MainSheet = MoveToward(Current.MainSheet, Sheet, (Sheet > Current.MainSheet ? Cfg.DinghySheetRate : TrimInRate) * Dt);
			else Out.MainSheet = MoveToward(Current.MainSheet, Sheet, Rate);
		}
		if (Set.bTrimJib && T.NumJibStrips > 0)
		{
			const double Foot = FootAngleFor(T.JibStrips, T.NumJibStrips, S.JibAngle * S.JibSide);
			Out.JibSheet = MoveToward(Current.JibSheet, Clamp((Foot - Cfg.JibMinAngleDeg * kDegToRad) / ((Cfg.JibMaxAngleDeg - Cfg.JibMinAngleDeg) * kDegToRad), 0.0, 1.0), Rate);
		}
		if (Set.bTrimJib && T.NumSpinStrips > 0)
		{
			const double Foot = FootAngleFor(T.SpinStrips, T.NumSpinStrips, S.SpinAngle * S.SpinSide);
			// Past the heel limit the trimmer blows the sheet at once (a broach starts in a second or two) and trims
			// back on as she comes upright; the main is eased with it (MainEase above).
			SpinEase = Clamp(SpinEase + (Excess > 0.0 ? 0.25 * Excess : -0.15) * Dt, 0.0, 1.0);
			const double Target = Clamp((Foot - 12.0 * kDegToRad) / (85.0 * kDegToRad), 0.0, 1.0);
			Out.SpinSheet = SpinEase > 0.0 ? std::max(MoveToward(Current.SpinSheet, std::max(Target, SpinEase), 4.0 * Rate), Target)
				: MoveToward(Current.SpinSheet, Target, Rate);
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
			double HikeRate = 0.8 * std::max(1.0, Cfg.CrewMoveSpeed / 1.6); // a dinghy sailor moves quicker than keelboat crew
			// ... and comes in off the hike at once when the sheet goes out, or she rolls to windward over the sailor.
			if (bDinghy) HikeRate *= 2.0;
			// A dinghy sailor slides back as she gets onto the plane: the bow stays up when she runs into the wave ahead and
			// the rudder stays in the water.
			if (Cfg.CrewAftRange > 0.0) Out.CrewAft = MoveToward(Current.CrewAft, Clamp((T.Froude - 0.5) / 0.4, 0.0, 1.0), Dt);
			Out.Hike = Clamp(Current.Hike + Clamp((Heel - 4.0 + 0.8 * HeelRate) / 4.0, -1.0, 1.0) * HikeRate * Dt, -1.0, 1.0);
		}
		return Out;
	}

	double FAutopilot::Update(const FBoatModel& Boat) const
	{
		const FBoatTelemetry& T = Boat.GetTelemetry();
		// Heading error: to raise the TWA on starboard tack (wind from +Y side), turn the bow away (to port).
		const double Error = WrapAngle(T.TrueWindAngle - TargetTWADeg * kDegToRad);
		const double YawRate = Boat.GetState().AngularVelocity.Z;
		// A good helmsman keeps the rudder a little short of its stall angle.
		const FBoatConfig& Cfg = Boat.GetConfig();
		double StallDeg = 14.0;
		for (const FFoilDef& F : Cfg.Foils) if (F.Role == EFoilRole::Rudder) StallDeg = F.Params.StallAngleDeg;
		const double Limit = bKeepShortOfStall ? std::min(MaxTiller, (StallDeg + 2.0) / Cfg.MaxRudderAngleDeg) : MaxTiller;
		// Heeled to port (wind from starboard) she wants to round up to starboard: hold the tiller against it (bow to port).
		const double Lean = Cfg.HeelYawCoef > 0.0 ? -HelmPerHeel * (T.Heel * kRadToDeg) / Cfg.MaxRudderAngleDeg : 0.0;
		return Clamp(Gain * Error + Lean - RateGain * YawRate, -Limit, Limit);
	}
}
