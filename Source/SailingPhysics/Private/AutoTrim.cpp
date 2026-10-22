#include "AutoTrim.h"

namespace Sailing
{
	namespace
	{
		// A dinghy sailor's answer to a puff (FAutoTrim::Update): felt a reaction time late, eased past a threshold.
		constexpr double PuffReactionSeconds = 0.4;
		constexpr double PuffSetUpSeconds = 30.0;  // the wind she is set up for: the last half minute's
		constexpr double PuffFromRatio = 1.2;      // a puff a fifth over it starts the ease ...
		constexpr double PuffFullRatio = 1.35;     // ... and this far over gets all of it
		constexpr double PuffEaseDeg = 20.0;
	}

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

		const double Rate = 0.8 * Set.RateScale * Dt; // sheets move at most 0.8 of full travel per second
		// A dinghy sailor sails her flat with the sheet in the hand: dumps it as soon as she heels past the limit (or starts
		// to roll toward it), and never trims in while she is still overpowered, even if the apparent wind comes forward.
		const bool bDinghy = Cfg.DinghyEasePerHeelDeg > 0.0;
		// Rolling to windward (a death roll starts so on a reach or a run) the sailor sheets in hard instead: it loads the
		// sail to leeward again.
		const double Windward = bDinghy ? std::max(-(Heel + 0.3 * HeelRate) - 3.0, 0.0) : 0.0;
		double Dump = bDinghy ? (std::max(Excess, 0.0) - Windward) * Cfg.DinghyEasePerHeelDeg * kDegToRad : 0.0;
		// Hiked flat in a big puff on a reach the heel hardly moves: the power goes into speed and a bow-down trim, and she
		// buries the bow and rounds up with the rudder at its stall angle (W1's 25-29 kn puffs on a 16 kn day). A dinghy
		// sailor answers the puff itself, not only the heel: feels it a reaction time late (0.4 s, a choice of how much to
		// ease; human simple reactions are about 0.2-0.3 s, choice reactions 0.4-0.5 s), eases the sheet in proportion to how
		// far it is over the wind she is set up for, and doesn't trim in again until it has passed. Not while she is upright
		// or rolling to windward over the hiked sailor: easing then starts the windward roll. (Dumping on the helm's pull as
		// well was tried: she slows, rolls to windward and nose-dives into the next wave.)
		double PuffEase = 0.0;
		if (bDinghy || Set.bEasePuffs)
		{
			if (FeltWind <= 0.0) FeltWind = SetUpWind = T.TrueWindSpeed;
			FeltWind += (T.TrueWindSpeed - FeltWind) * std::min(Dt / PuffReactionSeconds, 1.0);
			SetUpWind += (FeltWind - SetUpWind) * std::min(Dt / PuffSetUpSeconds, 1.0);
			const double Puff = Clamp((FeltWind / std::max(SetUpWind, 1.0) - PuffFromRatio) / (PuffFullRatio - PuffFromRatio), 0.0, 1.0);
			const double Leeward = SmoothStep(0.0, 6.0, Heel + 0.3 * HeelRate);
			PuffEase = PuffEaseDeg * Puff * Leeward * kDegToRad;
			Dump += PuffEase;
		}
		const bool bOverpowered = bDinghy && (Excess > -3.0 || PuffEase > kDegToRad);
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
			// A cat's crew with the boom eased past 55 deg sit on the windward hull, not to leeward (docs/hobie-downwind/): the
			// mainsheet runs from the boom's end, out beyond the leeward hull, back to the traveler on the rear beam, across
			// the leeward hull where they sat. On two hulls the light-air lean to leeward buys nothing.
			if (Cfg.bMultihull && std::fabs(S.BoomAngle) > 55.0 * kDegToRad) Out.Hike = std::max(Out.Hike, 0.0);
			// Tied up, or with no way on and not pressed, the crew sit in the middle (docs/dock-look/; Hike -0.5 is the
			// centreline whichever side is windward): in the slip, the apparent wind swung round her stern as she rolled, "a
			// little leeward heel" changed sides every roll and the crew shuttled across the cockpit, rocking her 4 deg every
			// 1.4 s; the same once the lines were off, drifting or backing out at under a knot.
			const bool bNoWay = std::fabs(T.SpeedThroughWater) < 0.8 * kKnot && std::fabs(T.Heel) < 8.0 * kDegToRad;
			if (!Boat.GetMooringLines().empty() || bNoWay) Out.Hike = MoveToward(Current.Hike, -0.5, HikeRate * Dt);
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
		// Making sternway (a wave stopped her head to wind and she is falling back) the rudder works the other way: a
		// helmsman reverses it, from 0.3 m/s astern to fully reversed by 0.8 (docs/wave-physics/: in the gale's sea the
		// maxi's tacks were stopped by a face and fell back at 1 to 4 kn, the wheel still hard over). Not for the moment a
		// dinghy stuffs her bow into a wave (0.5 kn astern for an instant): she is going again before the helm could act.
		const double Astern = Clamp(1.0 + 4.0 * std::min(T.ForwardSpeed + 0.3, 0.0), -1.0, 1.0);
		return Clamp(Astern * (Gain * Error + Lean - RateGain * YawRate), -Limit, Limit);
	}
}
