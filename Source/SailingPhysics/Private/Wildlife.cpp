#include "Wildlife.h"
#include "MiniJson.h"
#include <algorithm>
#include <cmath>

namespace Sailing
{
	namespace
	{
		constexpr double kPi = 3.14159265358979323846;
		constexpr double kTwoPi = 2.0 * kPi;
		constexpr double kG = 9.81;
		constexpr double kPathStep = 0.2;        // seconds between the leader's track points
		constexpr size_t kPathPoints = 220;      // 44 s of track: the longest line's tail
		constexpr int kMaxMembers = 40;          // a flock drawn bigger than this is drawn as 40 (rafts of 800 franklins)
		constexpr double kFadeSeconds = 3.0;
		constexpr double kRefreshSeconds = 5.0;  // how often the expected counts are worked out again
		constexpr double kCatchUpSeconds = 25.0; // a shortfall in a bird's flocks is made up over about this long
		constexpr double kPassShare = 0.35;      // share of travelling flocks whose first goal is beside the player's boat
		constexpr double kPassMinM = 40.0;       // how far off her side they pass
		constexpr double kPassMaxM = 120.0;
		constexpr double kRefPixel = 1.0 / 960.0;   // BirdSeenScale's reference pixel: 2 tan(45 deg) / 1920 (rad)
		constexpr double kRestLife = 600.0, kCircleLife = 240.0, kTravelLife = 180.0;   // mean stays (s), by what they start doing
		// A raft a boat is sailing at waits for her: one whose stay runs out while a boat inside kWaitAheadM is headed to pass
		// within its flush distance plus kWaitLaneM stays on (looked at again every kWaitSeconds), so it lifts when she gets
		// there. Without it, at 2.5 kn a raft 400 m off left first about 4 times in 10 (Nov 26 reel rehearsal).
		constexpr double kWaitAheadM = 500.0;
		constexpr double kWaitLaneM = 60.0;
		constexpr double kWaitSeconds = 15.0;
		constexpr double kPlacedLife = 1e9;      // a placed raft (-SailingBirdRaft) stays until a boat flushes it

		double WrapPi(double A)
		{
			while (A > kPi) A -= kTwoPi;
			while (A < -kPi) A += kTwoPi;
			return A;
		}
		double Clamp01(double X) { return X < 0.0 ? 0.0 : (X > 1.0 ? 1.0 : X); }
		double Smooth(double Edge0, double Edge1, double X)
		{
			const double T = Clamp01((X - Edge0) / (Edge1 - Edge0));
			return T * T * (3.0 - 2.0 * T);
		}
		/** A standard normal from two uniforms (Box-Muller). */
		double Normal(FPortableRandom& R)
		{
			const double U1 = std::max(1e-12, R.Uniform01());
			const double U2 = R.Uniform01();
			return std::sqrt(-2.0 * std::log(U1)) * std::cos(kTwoPi * U2);
		}
		double Exponential(FPortableRandom& R, double Mean) { return -Mean * std::log(std::max(1e-12, 1.0 - R.Uniform01())); }

		FBirdStyleParams MakeStyle(EBirdStyle S)
		{
			FBirdStyleParams P;
			switch (S)
			{
			case EBirdStyle::HeavyGlider:   // pelicans: about 45 km/h, a few slow beats then a long glide
				P.CruiseMs = 12.5; P.BeatHz = 1.3; P.FlapSeconds = 2.4; P.GlideSeconds = 6.0; P.AltMinM = 1.0; P.AltMaxM = 4.0;
				P.SpacingSpans = 1.2; P.Formation = EBirdFormation::Line; P.CircleShare = 0.25; P.CircleRadiusM = 60.0; P.CircleAltM = 120.0;
				P.TurnRateDeg = 20.0; P.Wander = 0.05; P.FlocksPerKm2 = 0.25; P.FlushM = 80.0; P.VeeShare = 0.3;
				break;
			case EBirdStyle::FlapHang:      // gulls: about 35 km/h, about 3 beats a second, hang in the wind
				P.CruiseMs = 9.7; P.BeatHz = 3.0; P.FlapSeconds = 3.0; P.GlideSeconds = 1.5; P.AltMinM = 3.0; P.AltMaxM = 15.0;
				P.SpacingSpans = 3.0; P.Formation = EBirdFormation::Loose; P.CircleShare = 0.2; P.CircleRadiusM = 30.0; P.CircleAltM = 20.0;
				P.TurnRateDeg = 45.0; P.Wander = 0.25; P.FlocksPerKm2 = 1.2; P.RestShare = 0.35; P.FlushM = 30.0;
				P.FlightAfterFlushM = 200.0;
				break;
			case EBirdStyle::HoverPlunge:   // terns, osprey, gannets: circle a feeding spot, dive from 5 to 20 m
				P.CruiseMs = 9.0; P.BeatHz = 3.5; P.FlapSeconds = 4.0; P.GlideSeconds = 1.0; P.AltMinM = 5.0; P.AltMaxM = 20.0;
				P.SpacingSpans = 4.0; P.Formation = EBirdFormation::Loose; P.CircleShare = 0.6; P.CircleRadiusM = 25.0; P.CircleAltM = 12.0;
				P.TurnRateDeg = 60.0; P.Wander = 0.2; P.FlocksPerKm2 = 0.5; P.FlushM = 30.0;
				break;
			case EBirdStyle::FastLow:       // cormorants, shags: about 55 km/h, rapid beats, a metre off the water
				P.CruiseMs = 15.0; P.BeatHz = 5.0; P.FlapSeconds = 1.0; P.GlideSeconds = 0.0; P.AltMinM = 0.7; P.AltMaxM = 2.5;
				P.SpacingSpans = 1.5; P.Formation = EBirdFormation::Line; P.TurnRateDeg = 25.0; P.Wander = 0.03;
				P.FlocksPerKm2 = 0.4; P.RestShare = 0.3; P.FlushM = 50.0; P.VeeShare = 0.5;
				break;
			case EBirdStyle::Shearing:      // shearwaters: banked arcs over the wave tops, stiff wings
				P.CruiseMs = 11.0; P.BeatHz = 4.0; P.FlapSeconds = 0.6; P.GlideSeconds = 3.0; P.AltMinM = 0.5; P.AltMaxM = 6.0;
				P.SpacingSpans = 6.0; P.Formation = EBirdFormation::Loose; P.TurnRateDeg = 50.0; P.Wander = 0.15;
				P.FlocksPerKm2 = 0.3; P.RestShare = 0.2; P.FlushM = 40.0;
				break;
			case EBirdStyle::Soaring:       // vultures, frigatebirds, raptors: circling high, almost no wingbeats
				P.CruiseMs = 11.0; P.BeatHz = 1.5; P.FlapSeconds = 0.8; P.GlideSeconds = 25.0; P.AltMinM = 80.0; P.AltMaxM = 400.0;
				P.SpacingSpans = 20.0; P.Formation = EBirdFormation::Circle; P.CircleShare = 0.85; P.CircleRadiusM = 60.0; P.CircleAltM = 200.0;
				P.TurnRateDeg = 25.0; P.Wander = 0.05; P.FlocksPerKm2 = 0.1;
				break;
			case EBirdStyle::Wading:        // herons, egrets: stand in the shallows; slow deep beats when flushed, about 35 km/h
				P.CruiseMs = 9.7; P.BeatHz = 2.2; P.FlapSeconds = 1.0; P.GlideSeconds = 0.0; P.AltMinM = 3.0; P.AltMaxM = 12.0;
				P.SpacingSpans = 3.0; P.Formation = EBirdFormation::Loose; P.TurnRateDeg = 30.0; P.Wander = 0.05;
				P.FlocksPerKm2 = 0.8; P.RestShare = 0.9; P.FlushM = 80.0; P.FlightAfterFlushM = 200.0;
				break;
			case EBirdStyle::Insect:        // swallows, martins, swifts: fast and jerky, low over the water
				P.CruiseMs = 9.0; P.BeatHz = 7.0; P.FlapSeconds = 0.5; P.GlideSeconds = 0.4; P.AltMinM = 1.0; P.AltMaxM = 6.0;
				P.SpacingSpans = 4.0; P.Formation = EBirdFormation::Loose; P.CircleShare = 0.7; P.CircleRadiusM = 30.0; P.CircleAltM = 5.0;
				P.TurnRateDeg = 180.0; P.Wander = 0.8; P.FlocksPerKm2 = 0.8;
				break;
			case EBirdStyle::Raft:          // ducks, coots: sit in rafts, flush ahead of the bow, fly low and fast
				P.CruiseMs = 16.0; P.BeatHz = 6.0; P.FlapSeconds = 1.0; P.GlideSeconds = 0.0; P.AltMinM = 1.0; P.AltMaxM = 6.0;
				P.SpacingSpans = 1.5; P.Formation = EBirdFormation::Vee; P.TurnRateDeg = 30.0; P.Wander = 0.05;
				P.FlocksPerKm2 = 0.4; P.RestShare = 0.85; P.FlushM = 60.0; P.FlightAfterFlushM = 350.0;
				break;
			default: break;
			}
			return P;
		}
	}

	namespace
	{
		/** A flock's mean stay in the band, from the mix of what its flocks start doing. */
		double MeanStaySeconds(EBirdStyle S)
		{
			const FBirdStyleParams& P = BirdStyleParams(S);
			return P.RestShare * kRestLife + (1.0 - P.RestShare) * (P.CircleShare * kCircleLife + (1.0 - P.CircleShare) * kTravelLife);
		}
	}

	const char* BirdStyleName(EBirdStyle S)
	{
		static const char* Names[] = { "heavy_glider", "flap_hang", "hover_plunge", "fast_low", "shearing", "soaring", "wading", "insect", "raft" };
		return int(S) < int(EBirdStyle::Count) ? Names[int(S)] : "?";
	}

	bool BirdStyleFromKey(const std::string& Key, EBirdStyle& Out)
	{
		for (int I = 0; I < int(EBirdStyle::Count); ++I)
		{
			if (Key == BirdStyleName(EBirdStyle(I))) { Out = EBirdStyle(I); return true; }
		}
		return false;
	}

	const FBirdStyleParams& BirdStyleParams(EBirdStyle S)
	{
		static const FBirdStyleParams Styles[] = {
			MakeStyle(EBirdStyle::HeavyGlider), MakeStyle(EBirdStyle::FlapHang), MakeStyle(EBirdStyle::HoverPlunge),
			MakeStyle(EBirdStyle::FastLow), MakeStyle(EBirdStyle::Shearing), MakeStyle(EBirdStyle::Soaring),
			MakeStyle(EBirdStyle::Wading), MakeStyle(EBirdStyle::Insect), MakeStyle(EBirdStyle::Raft) };
		return Styles[int(S) < int(EBirdStyle::Count) ? int(S) : 0];
	}

	uint32_t HabitatBits(const std::vector<std::string>& Words)
	{
		struct FWord { const char* W; uint32_t B; };
		static const FWord Map[] = {
			{"open_water", HabOpenWater}, {"bay", HabOpenWater}, {"calm_water", HabOpenWater}, {"low_over_water", HabOpenWater},
			{"passage", HabChannel}, {"channel", HabChannel},
			{"offshore", HabOffshore}, {"far_offshore", HabFarOffshore},
			{"shallows", HabShallows}, {"flats", HabShallows}, {"marsh", HabShallows},
			{"beach", HabShore}, {"surf", HabShore}, {"shore", HabShore}, {"over_shore", HabShore}, {"points", HabShore},
			{"coves", HabShore}, {"islands", HabShore}, {"jetty", HabShore}, {"logs", HabShore},
			{"marina", HabHarbour}, {"harbour", HabHarbour}, {"docks", HabHarbour}, {"boats", HabHarbour}, {"perch", HabHarbour},
			{"roost", HabHarbour},
			{"cliffs", HabCliffs}, {"sky", HabSky} };
		uint32_t Out = 0;
		for (const std::string& W : Words)
		{
			for (const FWord& M : Map) if (W == M.W) Out |= M.B;
		}
		return Out ? Out : uint32_t(HabOpenWater);
	}

	// ---- the table -------------------------------------------------------------------------------------------------

	bool FWildlifeTable::LoadText(const std::string& Json, std::string* OutError)
	{
		using MiniJson::FValue;
		*this = FWildlifeTable();
		FValue Root;
		std::string Err;
		if (!MiniJson::FReader(Json).Read(Root, Err) || Root.Type != FValue::EType::Object)
		{
			if (OutError) *OutError = Err.empty() ? std::string("not a JSON object") : Err;
			return false;
		}
		World = MiniJson::String(Root.Get("world"));
		if (const FValue* B = Root.Get("box"))
		{
			if (B->Type == FValue::EType::Array && B->Items.size() == 4)
			{
				for (int I = 0; I < 4; ++I) Box[I] = MiniJson::Number(&B->Items[size_t(I)], 0.0);
			}
		}
		const FValue* Rows = Root.Get("species");
		if (!Rows || Rows->Type != FValue::EType::Array)
		{
			if (OutError) *OutError = "no species list";
			return false;
		}
		for (const FValue& R : Rows->Items)
		{
			if (R.Type != FValue::EType::Object) continue;
			if (MiniJson::String(R.Get("kind")) != "bird") { ++OtherAnimals; continue; }
			FWildBird Row;
			Row.Id = MiniJson::String(R.Get("id"));
			Row.Name = MiniJson::String(R.Get("name"));
			if (!BirdStyleFromKey(MiniJson::String(R.Get("style")), Row.Style))
			{
				if (OutError) *OutError = Row.Id + ": unknown bird style " + MiniJson::String(R.Get("style"));
				return false;
			}
			Row.SizeM = MiniJson::Number(R.Get("size_m"), 1.0);
			Row.FlushM = MiniJson::Number(R.Get("flush_m"), 0.0);
			const FValue* M = R.Get("months");
			if (!M || M->Type != FValue::EType::Array || M->Items.size() != 12)
			{
				if (OutError) *OutError = Row.Id + ": months must hold 12 weights";
				return false;
			}
			for (int I = 0; I < 12; ++I) Row.Months[I] = MiniJson::Number(&M->Items[size_t(I)], 0.0);
			std::vector<std::string> Words;
			if (const FValue* H = R.Get("habitats"))
			{
				for (const FValue& W : H->Items) Words.push_back(MiniJson::String(&W));
			}
			Row.Habitats = HabitatBits(Words);
			const std::string Act = MiniJson::String(R.Get("activity"));
			if (!Act.empty()) Row.Activity = Act;
			if (const FValue* G = R.Get("group"))
			{
				Row.GroupTypical = std::max(1, int(MiniJson::Number(G->Get("typical"), 1.0)));
				Row.GroupP90 = std::max(Row.GroupTypical, int(MiniJson::Number(G->Get("p90"), double(Row.GroupTypical))));
			}
			Row.bRare = MiniJson::Bool(R.Get("rare"), false);
			Row.Water = MiniJson::String(R.Get("water"));
			Birds.push_back(Row);
		}
		return true;
	}

	const FWildBird* FWildlifeTable::Find(const std::string& Id) const
	{
		for (const FWildBird& B : Birds) if (B.Id == Id) return &B;
		return nullptr;
	}

	// ---- the day ---------------------------------------------------------------------------------------------------

	double ActivityAt(const std::string& Activity, double LocalHour, double Elev)
	{
		const bool bEvening = LocalHour >= 14.0;
		const double Day = Smooth(-6.0, -1.0, Elev);                  // 0 at night, 1 by sunrise
		const double LowSun = Day * (1.0 - Smooth(10.0, 20.0, Elev));  // dawn and dusk light
		if (Activity == "dawn_dusk") return 0.05 + 0.45 * Day + 0.8 * LowSun;
		if (Activity == "day_dusk") return 0.05 + 0.95 * Day + (bEvening ? 0.5 * LowSun : 0.0);
		if (Activity == "day_roost_dusk") return 0.1 + 0.9 * Day + (bEvening ? 0.5 * LowSun : 0.0);
		if (Activity == "midday_soaring")
		{
			// thermals: from about 10 am to 5 pm with the sun up past about 25 degrees
			const double Hours = Smooth(9.5, 10.5, LocalHour) * (1.0 - Smooth(16.5, 17.5, LocalHour));
			return 0.02 + 0.13 * Day + 0.85 * Hours * Smooth(20.0, 30.0, Elev);
		}
		if (Activity == "warm_day") return Day * (0.5 + 0.5 * Smooth(15.0, 25.0, Elev));
		if (Activity == "day_rafts_dusk_calls_night") return 0.3 + 0.5 * Day + 0.4 * LowSun;
		return 0.02 + 0.98 * Day;   // "day"
	}

	double WeatherFactor(EBirdStyle Style, const FWildlifeConditions& C)
	{
		double F = 1.0;
		if (C.RainMmH > 0.2) F *= C.RainMmH > 4.0 ? 0.25 : 0.5;
		if (C.WindKn > 20.0) F *= std::max(0.25, 1.0 - (C.WindKn - 20.0) / 15.0);
		switch (Style)
		{
		case EBirdStyle::Soaring:   // thermals need sun and light wind
			F *= Smooth(10.0, 25.0, C.SunElevationDeg) * (1.0 - 0.9 * Smooth(12.0, 18.0, C.WindKn));
			if (C.RainMmH > 0.2) F *= 0.2;
			break;
		case EBirdStyle::Insect:    // insects stay down in rain and wind
			if (C.RainMmH > 0.2) F *= 0.4;
			F *= 1.0 - 0.5 * Smooth(12.0, 20.0, C.WindKn);
			break;
		case EBirdStyle::Shearing:  // shearwaters like a breeze
			F *= 0.8 + 0.3 * Smooth(6.0, 15.0, C.WindKn);
			break;
		default: break;
		}
		return F;
	}

	FBirdLook BirdLookFor(const std::string& Id, EBirdStyle Style, bool* bListed)
	{
		if (bListed) *bListed = false;
		// sRGB field-guide tones taken to linear by eye (a white bird about 0.8, a gull's mantle 0.3-0.5, black 0.02-0.04).
		struct FRow { const char* Id; float U[3]; float D[3]; float Tips; };
		static const FRow Rows[] = {
			{ "american_white_pelican", { 0.80f, 0.80f, 0.78f }, { 0.78f, 0.78f, 0.76f }, 1.0f },   // black primaries
			{ "brown_pelican", { 0.17f, 0.15f, 0.13f }, { 0.11f, 0.10f, 0.09f }, 0.3f },
			{ "double_crested_cormorant", { 0.03f, 0.03f, 0.03f }, { 0.03f, 0.03f, 0.03f }, 0.0f },
			{ "coast_cormorants", { 0.03f, 0.03f, 0.03f }, { 0.03f, 0.03f, 0.03f }, 0.0f },
			{ "shag_cormorant", { 0.025f, 0.03f, 0.028f }, { 0.03f, 0.032f, 0.03f }, 0.0f },
			{ "ring_billed_gull", { 0.45f, 0.47f, 0.50f }, { 0.80f, 0.80f, 0.80f }, 1.0f },
			{ "franklins_gull", { 0.24f, 0.26f, 0.29f }, { 0.75f, 0.75f, 0.75f }, 0.6f },
			{ "laughing_gull", { 0.17f, 0.18f, 0.20f }, { 0.78f, 0.78f, 0.78f }, 1.0f },
			{ "yellow_legged_gull", { 0.30f, 0.32f, 0.35f }, { 0.80f, 0.80f, 0.80f }, 1.0f },
			{ "marseille_winter_gulls_terns", { 0.50f, 0.52f, 0.55f }, { 0.82f, 0.82f, 0.82f }, 0.8f },   // black-headed gulls mostly
			{ "forsters_tern", { 0.60f, 0.62f, 0.65f }, { 0.85f, 0.85f, 0.85f }, 0.3f },
			{ "coast_terns", { 0.58f, 0.60f, 0.63f }, { 0.85f, 0.85f, 0.85f }, 0.4f },
			{ "black_skimmer", { 0.02f, 0.02f, 0.02f }, { 0.80f, 0.80f, 0.80f }, 0.0f },
			{ "great_blue_heron", { 0.17f, 0.20f, 0.25f }, { 0.20f, 0.21f, 0.23f }, 0.8f },
			{ "egrets_green_heron", { 0.80f, 0.80f, 0.78f }, { 0.78f, 0.78f, 0.76f }, 0.0f },
			{ "coast_waders", { 0.20f, 0.18f, 0.15f }, { 0.50f, 0.48f, 0.45f }, 0.5f },
			{ "swallows_martin", { 0.02f, 0.03f, 0.07f }, { 0.40f, 0.30f, 0.20f }, 0.0f },
			{ "swifts", { 0.02f, 0.02f, 0.02f }, { 0.03f, 0.03f, 0.03f }, 0.0f },
			{ "vultures", { 0.03f, 0.03f, 0.03f }, { 0.05f, 0.05f, 0.05f }, 0.0f },
			{ "frigatebird", { 0.02f, 0.02f, 0.02f }, { 0.03f, 0.03f, 0.03f }, 0.0f },
			{ "cliff_raptors", { 0.08f, 0.06f, 0.04f }, { 0.35f, 0.30f, 0.25f }, 0.5f },
			{ "osprey", { 0.05f, 0.04f, 0.03f }, { 0.70f, 0.70f, 0.68f }, 0.5f },
			{ "northern_gannet", { 0.85f, 0.85f, 0.83f }, { 0.85f, 0.85f, 0.83f }, 1.0f },   // black wingtips
			{ "scopolis_shearwater", { 0.15f, 0.14f, 0.13f }, { 0.75f, 0.75f, 0.75f }, 0.0f },
			{ "yelkouan_shearwater", { 0.05f, 0.045f, 0.04f }, { 0.60f, 0.60f, 0.60f }, 0.0f },
			{ "lake_waterfowl", { 0.04f, 0.04f, 0.04f }, { 0.06f, 0.06f, 0.06f }, 0.0f },   // coots, scaup, ruddy ducks
		};
		FBirdLook L;
		for (const FRow& R : Rows)
		{
			if (Id != R.Id) continue;
			for (int K = 0; K < 3; ++K) { L.Upper[K] = R.U[K]; L.Under[K] = R.D[K]; }
			L.Tips = R.Tips;
			if (bListed) *bListed = true;
			return L;
		}
		auto Set = [&L](float U, float D, float Tips) { for (int K = 0; K < 3; ++K) { L.Upper[K] = U; L.Under[K] = D; } L.Tips = Tips; };
		switch (Style)
		{
		case EBirdStyle::HeavyGlider: Set(0.6f, 0.6f, 0.8f); break;
		case EBirdStyle::FlapHang: Set(0.4f, 0.8f, 1.0f); break;
		case EBirdStyle::HoverPlunge: Set(0.6f, 0.85f, 0.4f); break;
		case EBirdStyle::FastLow: Set(0.03f, 0.03f, 0.0f); break;
		case EBirdStyle::Shearing: Set(0.1f, 0.7f, 0.0f); break;
		case EBirdStyle::Soaring: Set(0.04f, 0.06f, 0.0f); break;
		case EBirdStyle::Wading: Set(0.3f, 0.35f, 0.5f); break;
		case EBirdStyle::Insect: Set(0.02f, 0.1f, 0.0f); break;
		case EBirdStyle::Raft: Set(0.05f, 0.07f, 0.0f); break;
		default: break;
		}
		return L;
	}

	double BirdSeenScale(double DistanceM, double PixelAngleRad)
	{
		// (Drawn size goes as the scale over the distance: the ramp below is gentle enough that it still grows as a bird nears.)
		const double D = std::max(0.0, DistanceM) * std::max(PixelAngleRad, 1e-6) / kRefPixel;
		return 1.0 + Smooth(100.0, 600.0, D);
	}

	FBirdBudget BirdBudgetForTier(int Tier)
	{
		FBirdBudget B;
		switch (Tier)
		{
		case 0: B.Far = 100; B.Mid = 20; B.Near = 4; break;   // (AWildlifeActor draws Low's as quads: no bodies)
		case 1: B.Far = 200; B.Mid = 40; B.Near = 6; break;
		case 2: B.Far = 300; B.Mid = 60; B.Near = 12; break;
		default: B.Far = 500; B.Mid = 100; B.Near = 20; break;
		}
		return B;
	}

	// ---- the habitat map -------------------------------------------------------------------------------------------

	void FWildlifeHabitatMap::Build(const FWildlifeWorld& W, double CenterN, double CenterE, double HalfSizeM, double CellM)
	{
		CN = CenterN; CE = CenterE; Half = HalfSizeM; Cell = CellM;
		Cells = std::max(2, int(std::ceil(2.0 * Half / Cell)));
		const size_t Count = size_t(Cells) * size_t(Cells);
		CellBits.assign(Count, 0u);
		CellHeight.assign(Count, 0.0f);
		CellTop.assign(Count, 0.0f);
		std::vector<float> Dist(Count, 1e9f);   // cells to the nearest cell of the other kind (water to land, land to water)
		auto Top = [&](double North, double East)
		{
			const double G = W.HeightAt ? W.HeightAt(North, East) : -10.0;
			return std::max(0.0, G + (W.CanopyAt && G > 0.0 ? W.CanopyAt(North, East) : 0.0));
		};
		for (int J = 0; J < Cells; ++J)
		{
			for (int I = 0; I < Cells; ++I)
			{
				const double North = CN - Half + (J + 0.5) * Cell, East = CE - Half + (I + 0.5) * Cell;
				const size_t K = size_t(J) * size_t(Cells) + size_t(I);
				CellHeight[K] = float(W.HeightAt ? W.HeightAt(North, East) : -10.0);
				// The highest ground or canopy on a 5 x 5 grid over the cell (12.5 m apart in 50 m cells): the coast grids
				// are 10 to 25 m, and Marseille's cliffs climb 30 m between a cell's corners. A crest between two samples
				// can stand above both by up to half the steepest step between neighbours: that margin goes on top.
				double S[5][5];
				double T = 0.0, Step = 0.0;
				for (int A = 0; A <= 4; ++A)
				{
					for (int B = 0; B <= 4; ++B)
					{
						S[A][B] = Top(North + (A / 4.0 - 0.5) * Cell, East + (B / 4.0 - 0.5) * Cell);
						T = std::max(T, S[A][B]);
						if (A > 0) Step = std::max(Step, std::fabs(S[A][B] - S[A - 1][B]));
						if (B > 0) Step = std::max(Step, std::fabs(S[A][B] - S[A][B - 1]));
					}
				}
				CellTop[K] = float(T + 0.5 * Step);
			}
		}
		// Seeds: cells with a neighbour of the other kind are on the waterline.
		auto Wet = [&](int I, int J) { return CellHeight[size_t(J) * size_t(Cells) + size_t(I)] < 0.0f; };
		for (int J = 0; J < Cells; ++J)
		{
			for (int I = 0; I < Cells; ++I)
			{
				const bool bW = Wet(I, J);
				const bool bEdge = (I > 0 && Wet(I - 1, J) != bW) || (I + 1 < Cells && Wet(I + 1, J) != bW) ||
					(J > 0 && Wet(I, J - 1) != bW) || (J + 1 < Cells && Wet(I, J + 1) != bW);
				if (bEdge) Dist[size_t(J) * size_t(Cells) + size_t(I)] = 0.5f;
			}
		}
		// Two-pass chamfer distance (3-4 weights over 3) from the waterline.
		const float A = 1.0f, D = 1.41421356f;
		for (int J = 0; J < Cells; ++J)
		{
			for (int I = 0; I < Cells; ++I)
			{
				float& V = Dist[size_t(J) * size_t(Cells) + size_t(I)];
				if (I > 0) V = std::min(V, Dist[size_t(J) * size_t(Cells) + size_t(I - 1)] + A);
				if (J > 0) V = std::min(V, Dist[size_t(J - 1) * size_t(Cells) + size_t(I)] + A);
				if (I > 0 && J > 0) V = std::min(V, Dist[size_t(J - 1) * size_t(Cells) + size_t(I - 1)] + D);
				if (I + 1 < Cells && J > 0) V = std::min(V, Dist[size_t(J - 1) * size_t(Cells) + size_t(I + 1)] + D);
			}
		}
		for (int J = Cells - 1; J >= 0; --J)
		{
			for (int I = Cells - 1; I >= 0; --I)
			{
				float& V = Dist[size_t(J) * size_t(Cells) + size_t(I)];
				if (I + 1 < Cells) V = std::min(V, Dist[size_t(J) * size_t(Cells) + size_t(I + 1)] + A);
				if (J + 1 < Cells) V = std::min(V, Dist[size_t(J + 1) * size_t(Cells) + size_t(I)] + A);
				if (I + 1 < Cells && J + 1 < Cells) V = std::min(V, Dist[size_t(J + 1) * size_t(Cells) + size_t(I + 1)] + D);
				if (I > 0 && J + 1 < Cells) V = std::min(V, Dist[size_t(J + 1) * size_t(Cells) + size_t(I - 1)] + D);
			}
		}
		for (int J = 0; J < Cells; ++J)
		{
			for (int I = 0; I < Cells; ++I)
			{
				const size_t K = size_t(J) * size_t(Cells) + size_t(I);
				const double H = CellHeight[K];
				const double ShoreM = Dist[K] >= 1e8f ? 1e9 : double(Dist[K]) * Cell;
				uint32_t B = HabSky;
				if (H < 0.0)
				{
					const double Depth = -H;
					if (Depth > 1.5) B |= HabOpenWater; else B |= HabShallows;
					if (Depth > 6.0) B |= HabChannel;
					if (ShoreM >= 2000.0) B |= HabOffshore;
					if (ShoreM >= 3500.0 || Depth > 80.0) B |= HabFarOffshore | HabOffshore;
					if (ShoreM <= 150.0) B |= HabShore;
				}
				else
				{
					if (ShoreM <= 150.0) B |= HabShore;
					if (H >= 20.0 && ShoreM <= 300.0) B |= HabCliffs;
				}
				if (W.IsHarbour)
				{
					const double North = CN - Half + (J + 0.5) * Cell, East = CE - Half + (I + 0.5) * Cell;
					if (W.IsHarbour(North, East)) B |= HabHarbour;
				}
				CellBits[K] = B;
			}
		}
	}

	int FWildlifeHabitatMap::Index(double North, double East) const
	{
		if (Cells <= 0) return -1;
		const int I = int(std::floor((East - (CE - Half)) / Cell));
		const int J = int(std::floor((North - (CN - Half)) / Cell));
		if (I < 0 || J < 0 || I >= Cells || J >= Cells) return -1;
		return J * Cells + I;
	}

	uint32_t FWildlifeHabitatMap::BitsAt(double North, double East) const
	{
		const int K = Index(North, East);
		return K < 0 ? 0u : CellBits[size_t(K)];
	}

	double FWildlifeHabitatMap::HeightAt(double North, double East) const
	{
		const int K = Index(North, East);
		return K < 0 ? 0.0 : double(CellHeight[size_t(K)]);
	}

	double FWildlifeHabitatMap::TopAt(double North, double East) const
	{
		const int K = Index(North, East);
		return K < 0 ? 0.0 : double(CellTop[size_t(K)]);
	}

	double FWildlifeHabitatMap::AreaKm2(uint32_t Bits, double North, double East, double RadiusM) const
	{
		if (Cells <= 0) return 0.0;
		const int R = int(std::ceil(RadiusM / Cell));
		const int K0 = Index(North, East);
		if (K0 < 0) return 0.0;
		const int I0 = K0 % Cells, J0 = K0 / Cells;
		int Hits = 0;
		for (int J = std::max(0, J0 - R); J <= std::min(Cells - 1, J0 + R); ++J)
		{
			for (int I = std::max(0, I0 - R); I <= std::min(Cells - 1, I0 + R); ++I)
			{
				const double DN = (J - J0) * Cell, DE = (I - I0) * Cell;
				if (DN * DN + DE * DE > RadiusM * RadiusM) continue;
				if (CellBits[size_t(J) * size_t(Cells) + size_t(I)] & Bits) ++Hits;
			}
		}
		return Hits * Cell * Cell * 1e-6;
	}

	void FWildlifeHabitatMap::Histogram(double North, double East, double RadiusM, std::vector<std::pair<uint32_t, double>>& Out) const
	{
		Out.clear();
		if (Cells <= 0) return;
		const int R = int(std::ceil(RadiusM / Cell));
		const int K0 = Index(North, East);
		if (K0 < 0) return;
		const int I0 = K0 % Cells, J0 = K0 / Cells;
		const double CellKm2 = Cell * Cell * 1e-6;
		for (int J = std::max(0, J0 - R); J <= std::min(Cells - 1, J0 + R); ++J)
		{
			for (int I = std::max(0, I0 - R); I <= std::min(Cells - 1, I0 + R); ++I)
			{
				const double DN = (J - J0) * Cell, DE = (I - I0) * Cell;
				if (DN * DN + DE * DE > RadiusM * RadiusM) continue;
				const uint32_t B = CellBits[size_t(J) * size_t(Cells) + size_t(I)];
				bool bFound = false;
				for (auto& P : Out) if (P.first == B) { P.second += CellKm2; bFound = true; break; }
				if (!bFound) Out.push_back({B, CellKm2});
			}
		}
	}

	double FWildlifeHabitatMap::AreaOf(uint32_t Bits, const std::vector<std::pair<uint32_t, double>>& H)
	{
		double A = 0.0;
		for (const auto& P : H) if (P.first & Bits) A += P.second;
		return A;
	}

	bool FWildlifeHabitatMap::Pick(uint32_t Bits, double North, double East, double MinM, double MaxM, FPortableRandom& Rng,
		double& OutN, double& OutE) const
	{
		for (int Try = 0; Try < 48; ++Try)
		{
			// uniform over the annulus' area
			const double R = std::sqrt(Rng.Uniform(MinM * MinM, MaxM * MaxM));
			const double A = Rng.Uniform(0.0, kTwoPi);
			const double PN = North + R * std::cos(A), PE = East + R * std::sin(A);
			if (BitsAt(PN, PE) & Bits) { OutN = PN; OutE = PE; return true; }
		}
		return false;
	}

	bool FWildlifeHabitatMap::PickToward(uint32_t Bits, double North, double East, double HeadingRad, double DistM,
		FPortableRandom& Rng, double& OutN, double& OutE) const
	{
		for (int Try = 0; Try < 24; ++Try)
		{
			const double A = HeadingRad + Rng.Uniform(-0.6, 0.6) * (1.0 + Try / 8.0);
			const double R = DistM * Rng.Uniform(0.6, 1.3);
			const double PN = North + R * std::cos(A), PE = East + R * std::sin(A);
			if (BitsAt(PN, PE) & Bits) { OutN = PN; OutE = PE; return true; }
		}
		return Pick(Bits, North, East, 0.3 * DistM, 1.5 * DistM, Rng, OutN, OutE);
	}

	// ---- the flocks ------------------------------------------------------------------------------------------------

	void FBirdFlocks::Reset(const FWildlifeTable& InTable, uint64_t Seed)
	{
		Table = InTable;
		BaseSeed = Seed;
		Rng.Reseed(Seed);
		NextFlockId = 1;
		Flocks.clear();
		Drawn.clear();
		NewSplashes.clear();
		Expected.assign(Table.Birds.size(), 0.0);
		Stay.resize(Table.Birds.size());
		for (size_t I = 0; I < Table.Birds.size(); ++I) Stay[I] = MeanStaySeconds(Table.Birds[I].Style);
		ExpectedT = 1e9;
		bFilled = false;
		St = FStats();
		Rafts.clear();
	}

	bool FBirdFlocks::PlaceRaft(const std::string& BirdId, double North, double East, int Count)
	{
		for (size_t I = 0; I < Table.Birds.size(); ++I)
		{
			if (Table.Birds[I].Id != BirdId) continue;
			FRaftPlace R;
			R.Bird = int(I);
			R.North = North;
			R.East = East;
			R.Count = Count;
			Rafts.push_back(R);
			return true;
		}
		return false;
	}

	int FBirdFlocks::GroupSize(const FWildBird& B, FPortableRandom& R) const
	{
		// Log-normal through the table's usual count (the median) and its 9-in-10 count.
		const double Sigma = std::log(std::max(1.0, double(B.GroupP90) / std::max(1, B.GroupTypical))) / 1.2816;
		const double Z = std::max(-2.0, std::min(2.5, Normal(R)));
		const double N = B.GroupTypical * std::exp(Sigma * Z);
		return std::max(1, std::min(kMaxMembers, int(std::lround(N))));
	}

	double FBirdFlocks::ExpectedFlocksFor(int I, const FWildlifeConditions& C, double Area) const
	{
		if (I < 0 || I >= int(Table.Birds.size())) return 0.0;
		const FWildBird& B = Table.Birds[size_t(I)];
		const FBirdStyleParams& P = BirdStyleParams(B.Style);
		const double Month = B.Months[std::max(1, std::min(12, C.Month)) - 1];
		if (Month <= 0.0) return 0.0;
		return P.FlocksPerKm2 * DensityScale * Area * Month * ActivityAt(B.Activity, C.LocalHour, C.SunElevationDeg) *
			WeatherFactor(B.Style, C) * (B.bRare ? 0.15 : 1.0);
	}

	double FBirdFlocks::ExpectedFlocks(int I, const FWildlifeConditions& C, const FWildlifeHabitatMap& Map, double North, double East) const
	{
		if (I < 0 || I >= int(Table.Birds.size())) return 0.0;
		return ExpectedFlocksFor(I, C, Map.AreaKm2(Table.Birds[size_t(I)].Habitats, North, East, FarM));
	}

	void FBirdFlocks::RefreshExpected(const FWildlifeConditions& C, const FWildlifeHabitatMap& Map, const FBirdObservers& Obs)
	{
		std::vector<std::pair<uint32_t, double>> H;
		Map.Histogram(Obs.CamNorth, Obs.CamEast, FarM, H);
		Expected.resize(Table.Birds.size());
		for (size_t I = 0; I < Table.Birds.size(); ++I)
			Expected[I] = ExpectedFlocksFor(int(I), C, FWildlifeHabitatMap::AreaOf(Table.Birds[I].Habitats, H));
		ExpectedT = 0.0;
		LastCamN = Obs.CamNorth;
		LastCamE = Obs.CamEast;
	}

	int FBirdFlocks::FlockCountOf(int I) const
	{
		int N = 0;
		for (const FFlock& F : Flocks) N += F.Bird == I && !F.bLeaving;
		return N;
	}

	int FBirdFlocks::BirdCountOf(int I) const
	{
		int N = 0;
		for (const FFlock& F : Flocks) if (F.Bird == I) N += int(F.Members.size());
		return N;
	}

	void FBirdFlocks::NewGoal(FFlock& F, const FWildlifeHabitatMap& Map, double DistM)
	{
		const FWildBird& B = Table.Birds[size_t(F.Bird)];
		double GN = F.N + DistM * std::cos(F.Heading), GE = F.E + DistM * std::sin(F.Heading);
		// keep travelling flocks over their habitat and inside the map (the camera's 2 km and the goals past it)
		const double Turn = F.Rng.Uniform(-1.2, 1.2);
		if (!Map.PickToward(B.Habitats, F.N, F.E, F.Heading + Turn, DistM, F.Rng, GN, GE))
		{
			GN = Map.CenterNorth() + F.Rng.Uniform(-1.0, 1.0) * 0.5 * Map.HalfSize();
			GE = Map.CenterEast() + F.Rng.Uniform(-1.0, 1.0) * 0.5 * Map.HalfSize();
		}
		F.GoalN = GN;
		F.GoalE = GE;
	}

	bool FBirdFlocks::Spawn(int I, const FWildlifeConditions& /*C*/, const FBirdObservers& Obs, const FWildlifeHabitatMap& Map, double MinM, double MaxM,
		const FRaftPlace* Place)
	{
		const FWildBird& B = Table.Birds[size_t(I)];
		const FBirdStyleParams& P = BirdStyleParams(B.Style);
		// a placed raft sits where it was asked to, or nowhere (on land, or a wader out of its depth)
		if (Place && !CanRestAt(B, Map, Place->North, Place->East)) return false;
		FFlock F;
		F.Bird = I;
		F.Seed = HashCombine(BaseSeed, NextFlockId++);
		F.Rng.Reseed(F.Seed);
		bool bRest = Place || (P.RestShare > 0.0 && F.Rng.Uniform01() < P.RestShare);
		double SN = 0.0, SE = 0.0;
		if (Place)
		{
			SN = Place->North;
			SE = Place->East;
		}
		else if (bRest)
		{
			// on the water (or standing in the shallows and at the water's edge for waders), inside the bird's habitats
			uint32_t Where = B.Habitats & (B.Style == EBirdStyle::Wading ? uint32_t(HabShallows | HabShore | HabHarbour)
				: uint32_t(HabOpenWater | HabChannel | HabOffshore | HabFarOffshore | HabShallows | HabShore | HabHarbour));
			if (!Where) Where = B.Habitats;
			bool bFound = false;
			for (int Try = 0; Try < 4 && !bFound; ++Try)
				bFound = Map.Pick(Where, Obs.CamNorth, Obs.CamEast, MinM, MaxM, F.Rng, SN, SE) && CanRestAt(B, Map, SN, SE);
			bRest = bFound;   // nowhere to sit here: this one is flying
		}
		if (!bRest && !Map.Pick(B.Habitats, Obs.CamNorth, Obs.CamEast, MinM, MaxM, F.Rng, SN, SE)) return false;
		F.N = SN; F.E = SE;
		F.Heading = F.Rng.Uniform(0.0, kTwoPi);
		F.Side = F.Rng.Uniform01() < 0.5 ? -1 : 1;
		F.bResting = bRest;
		F.bCircling = !bRest && F.Rng.Uniform01() < P.CircleShare;
		F.Life = Place ? kPlacedLife : Exponential(F.Rng, bRest ? kRestLife : (F.bCircling ? kCircleLife : kTravelLife));
		F.Speed = P.CruiseMs;
		F.TargetUp = F.bCircling ? P.CircleAltM * F.Rng.Uniform(0.7, 1.3) : F.Rng.Uniform(P.AltMinM, P.AltMaxM);
		F.Up = bRest ? 0.0 : F.TargetUp + Map.TopAt(SN, SE);
		F.Fade = bFilled && !Place ? 0.0 : 1.0;
		F.bFirstFill = !bFilled;
		F.bPlaced = Place != nullptr;
		NewGoal(F, Map, F.Rng.Uniform(800.0, 2500.0));
		// some travellers come by the boat: their first goal is beside her, 40 to 120 m off (met, not only seen far off)
		const FBirdObservers::FBoat* Player = PlayerBoat(Obs);
		if (!bRest && !F.bCircling && Player && F.Rng.Uniform01() < kPassShare)
		{
			const double ToBoat = std::atan2(Player->East - F.E, Player->North - F.N);
			const double Side = (F.Rng.Uniform01() < 0.5 ? -1.0 : 1.0) * F.Rng.Uniform(kPassMinM, kPassMaxM);
			const double PN = Player->North + Side * -std::sin(ToBoat), PE = Player->East + Side * std::cos(ToBoat);
			if (Map.BitsAt(PN, PE) & B.Habitats) { F.GoalN = PN; F.GoalE = PE; F.bPassing = true; }
			// Placed as the camera arrived: already partway in, 80 m to 1 km short of her (a flock from the band's edge
			// takes 2 to 3 minutes to come by, and the first minutes on the water would have no bird near).
			const double Len = std::hypot(F.GoalN - F.N, F.GoalE - F.E);
			if (F.bPassing && F.bFirstFill && Len > 80.0)
			{
				const double Back = std::min(Len, F.Rng.Uniform(80.0, 1000.0));
				const double NN = F.GoalN - (F.GoalN - F.N) / Len * Back, NE = F.GoalE - (F.GoalE - F.E) / Len * Back;
				if (Map.BitsAt(NN, NE) & B.Habitats)
				{
					F.N = NN; F.E = NE;
					F.Up = F.TargetUp + Map.TopAt(NN, NE);
				}
			}
		}
		F.Heading = std::atan2(F.GoalE - F.E, F.GoalN - F.N);
		const int Count = Place && Place->Count > 0 ? std::min(kMaxMembers, Place->Count) : GroupSize(B, F.Rng);
		const double Span = B.SizeM;
		const double Spacing = (P.SpacingSpans + 1.0) * Span;
		const double R = Spacing * std::sqrt(double(Count));
		const EBirdFormation Form = (Count >= 6 && F.Rng.Uniform01() < P.VeeShare) ? EBirdFormation::Vee : P.Formation;
		F.Members.resize(size_t(Count));
		for (int K = 0; K < Count; ++K)
		{
			FMember& M = F.Members[size_t(K)];
			if (F.bCircling || Form == EBirdFormation::Circle)
			{
				M.OffA = P.CircleRadiusM * F.Rng.Uniform(0.5, 1.5);    // radius
				M.OffB = F.Rng.Uniform(0.0, kTwoPi);                  // phase
				M.OffC = F.Rng.Uniform(-0.2, 0.2) * F.TargetUp;       // height
			}
			else if (bRest)
			{
				const double RR = R * std::sqrt(F.Rng.Uniform01()), AA = F.Rng.Uniform(0.0, kTwoPi);
				M.OffA = RR * std::cos(AA);
				M.OffB = RR * std::sin(AA);
				M.OffC = 0.0;
			}
			else if (Form == EBirdFormation::Line)
			{
				M.OffA = K * Spacing * F.Rng.Uniform(0.9, 1.1);                      // back along the path
				M.OffB = F.Side * K * 0.15 * Spacing + F.Rng.Uniform(-0.2, 0.2) * Span; // a slight echelon
				M.OffC = F.Rng.Uniform(-0.1, 0.1) * Span;
			}
			else if (Form == EBirdFormation::Vee)
			{
				const int Rank = (K + 1) / 2, Arm = K % 2 ? 1 : -1;
				M.OffA = Rank * Spacing * 0.8;
				M.OffB = Arm * Rank * Spacing * 0.6;
				M.OffC = F.Rng.Uniform(-0.1, 0.1) * Span;
			}
			else
			{
				M.OffA = K == 0 ? 0.0 : F.Rng.Uniform(0.0, 2.0 * R);
				M.OffB = K == 0 ? 0.0 : F.Rng.Uniform(-R, R);
				M.OffC = K == 0 ? 0.0 : F.Rng.Uniform(-0.3, 0.3) * R;
			}
			M.CycleT = F.Rng.Uniform(0.0, P.FlapSeconds + P.GlideSeconds);
			if (Form == EBirdFormation::Line || Form == EBirdFormation::Vee)
			{
				// in a line each bird beats where the one ahead did: the flap runs back down the line
				M.CycleT = std::fmod(F.Members[0].CycleT - M.OffA / std::max(1.0, P.CruiseMs) + 1000.0 * (P.FlapSeconds + P.GlideSeconds),
					std::max(0.01, P.FlapSeconds + P.GlideSeconds));
			}
			M.Phase = F.Rng.Uniform01();
			M.Scale = F.Rng.Uniform(0.92, 1.08);
			M.State = bRest ? (B.Style == EBirdStyle::Wading ? EBirdState::Standing : EBirdState::OnWater)
				: (F.bCircling ? EBirdState::Circling : EBirdState::Flying);
			M.Heading = F.Heading;
		}
		// a straight track behind the leader, so the line is in shape from the first frame
		F.Path.clear();
		for (int K = int(kPathPoints) - 1; K >= 0; --K)
		{
			const double Back = K * kPathStep * F.Speed;
			F.Path.push_back({F.N - Back * std::cos(F.Heading), F.E - Back * std::sin(F.Heading), F.Up, F.Heading});
		}
		// Members' places from the first frame.
		Flocks.push_back(std::move(F));
		StepMembers(Flocks.back(), 0.0, Map);
		++St.Spawned;
		return true;
	}

	void FBirdFlocks::Update(double Dt, const FWildlifeConditions& C, const FBirdObservers& Obs, const FWildlifeHabitatMap& Map)
	{
		NewSplashes.clear();
		if (Table.Birds.empty() || !Map.IsBuilt()) { Drawn.clear(); return; }
		Dt = std::max(0.0, std::min(Dt, 0.5));
		const double Moved = std::hypot(Obs.CamNorth - LastCamN, Obs.CamEast - LastCamE);
		ExpectedT += Dt;
		if (ExpectedT >= kRefreshSeconds || Moved > 200.0 || Expected.size() != Table.Birds.size()) RefreshExpected(C, Map, Obs);
		if (bFilled && Moved > 3000.0)
		{
			// a jump (a new launch spot, a teleport): start again round the camera
			Flocks.clear();
			bFilled = false;
		}

		if (!bFilled)
		{
			// The first fill: every bird at its expected count, anywhere in the bands.
			for (int I = 0; I < int(Table.Birds.size()); ++I)
			{
				const double E = Expected[size_t(I)];
				int Want = int(std::floor(E));
				if (Rng.Uniform01() < E - Want) ++Want;
				for (int K = 0; K < Want; ++K) Spawn(I, C, Obs, Map, NearM, FarM);
			}
			bFilled = true;
			// then the placed rafts (after the fill, so the rest are laid as they would be without them)
			for (FRaftPlace& R : Rafts) R.State = Spawn(R.Bird, C, Obs, Map, 0.0, 0.0, &R) ? 1 : -1;
		}
		else
		{
			// Births keep each bird near its expected count: arrivals making up the shortfall over kCatchUpSeconds, plus a
			// slow turnover (new flocks coming in from beyond the band) while the count is about right.
			for (int I = 0; I < int(Table.Birds.size()); ++I)
			{
				const double E = Expected[size_t(I)];
				if (E <= 0.0) continue;
				const double Have = FlockCountOf(I);
				// arrivals at the expected count over a flock's stay (as these flocks have stayed so far: travellers cross the
				// band); held to the count by a proportional term (stays measured early on run short), a shortfall of more
				// than one made up sooner
				const double Hold = std::max(0.0, std::min(4.0, 1.0 + 4.0 * (E - Have) / std::max(1.0, E)));
				const double Rate = E / std::max(30.0, Stay[size_t(I)]) * Hold + std::max(0.0, E - Have - 1.0) / kCatchUpSeconds;
				if (Rng.Uniform01() < Rate * Dt) Spawn(I, C, Obs, Map, SpawnMinM, FarM);
			}
		}

		// (Held time steps nothing: a zero step would put every bird back in its slot.)
		++Frame;
		if (Dt > 0.0) for (FFlock& F : Flocks) StepFlock(F, Dt, C, Obs, Map);

		// Retire flocks that left, faded out, or that the camera left behind.
		const size_t Before = Flocks.size();
		Flocks.erase(std::remove_if(Flocks.begin(), Flocks.end(), [&](const FFlock& F)
		{
			const double D = std::hypot(F.N - Obs.CamNorth, F.E - Obs.CamEast);
			const bool bGone = D > FarM + 300.0 || (F.bLeaving && F.Fade <= 0.0);
			if (bGone && !F.bLeaving) EndStay(F);
			return bGone;
		}), Flocks.end());
		St.Retired += int(Before - Flocks.size());
		BuildDraw(Obs);
	}

	const FBirdObservers::FBoat* FBirdFlocks::PlayerBoat(const FBirdObservers& Obs) const
	{
		for (const FBirdObservers::FBoat& Boat : Obs.Boats) if (Boat.bPlayer) return &Boat;
		return nullptr;
	}

	bool FBirdFlocks::CanRestAt(const FWildBird& B, const FWildlifeHabitatMap& Map, double North, double East) const
	{
		const double H = Map.HeightAt(North, East);
		// herons and egrets stand knee deep or on the bank (the game stands them on the ground); the rest sit on water
		if (B.Style == EBirdStyle::Wading) return H > -1.0 && H < 2.0 && (Map.BitsAt(North, East) & (HabShallows | HabShore));
		return H < 0.0;
	}

	void FBirdFlocks::EndStay(const FFlock& F)
	{
		// flocks from the first fill were met partway through their stay: their ages say less
		if (F.bFirstFill || F.bPlaced || F.Bird < 0 || F.Bird >= int(Stay.size())) return;
		Stay[size_t(F.Bird)] += 0.15 * (F.Age - Stay[size_t(F.Bird)]);
	}

	bool FBirdFlocks::BoatClosingOn(const FFlock& F, const FBirdObservers& Obs) const
	{
		const FWildBird& B = Table.Birds[size_t(F.Bird)];
		const double Flush = B.FlushM > 0.0 ? B.FlushM : BirdStyleParams(B.Style).FlushM;
		for (const FBirdObservers::FBoat& Boat : Obs.Boats)
		{
			if (Boat.SpeedMs < 0.3) continue;
			// the raft in her frame: how far ahead, and how far off the line she is sailing
			const double DN = F.N - Boat.North, DE = F.E - Boat.East;
			const double Along = DN * std::cos(Boat.HeadingRad) + DE * std::sin(Boat.HeadingRad);
			const double Across = -DN * std::sin(Boat.HeadingRad) + DE * std::cos(Boat.HeadingRad);
			if (Along > 0.0 && Along < kWaitAheadM && std::fabs(Across) < Flush + kWaitLaneM) return true;
		}
		return false;
	}

	bool FBirdFlocks::CheckFlush(FFlock& F, const FBirdObservers& Obs, const FWildlifeHabitatMap& Map, bool bForce)
	{
		if (!F.bResting || F.bFlushed) return false;
		const FWildBird& B = Table.Birds[size_t(F.Bird)];
		const FBirdStyleParams& P = BirdStyleParams(B.Style);
		const double Flush = B.FlushM > 0.0 ? B.FlushM : P.FlushM;
		const FBirdObservers::FBoat* Near = nullptr;
		double Best = 1e36;   // squared
		// (every resting flock, every frame, against every boat: squares, and a boat clear of the flock's reach skipped)
		double Reach = 0.0;
		for (const FMember& M : F.Members) Reach = std::max(Reach, (M.N - F.N) * (M.N - F.N) + (M.E - F.E) * (M.E - F.E));
		Reach = std::sqrt(Reach);
		for (const FBirdObservers::FBoat& Boat : Obs.Boats)
		{
			const double CN = F.N - Boat.North, CE = F.E - Boat.East;
			if (!bForce && std::sqrt(CN * CN + CE * CE) > Reach + Flush) continue;
			for (const FMember& M : F.Members)
			{
				const double DN = M.N - Boat.North, DE = M.E - Boat.East;
				const double D2 = DN * DN + DE * DE;
				if (D2 < Best) { Best = D2; Near = &Boat; }
			}
		}
		if (!Near || (!bForce && Best > Flush * Flush)) return false;
		// They lift a few at a time, nearest first, and fly away from the bow.
		F.bFlushed = true;
		F.bResting = false;
		F.bCircling = false;
		++St.Flushes;
		const double Away = std::atan2(F.E - Near->East, F.N - Near->North);
		const double Ahead = Near->HeadingRad;
		// mostly away from the boat, swung toward where it is heading (it flies off ahead, not back across the bow)
		const double Dir = Away + 0.5 * WrapPi(Ahead - Away) * (Near->SpeedMs > 0.5 ? 0.5 : 0.0);
		F.Heading = Dir;
		F.Speed = P.CruiseMs;
		F.TargetUp = std::max(1.0, std::min(P.AltMaxM, P.AltMinM + 2.0));
		const double FlyM = P.FlightAfterFlushM * F.Rng.Uniform(0.7, 1.35);
		F.GoalN = F.N + FlyM * std::cos(Dir);
		F.GoalE = F.E + FlyM * std::sin(Dir);
		// settle again where they can sit: the nearest such cell about that far along that way
		for (int Try = 0; Try < 12 && !CanRestAt(B, Map, F.GoalN, F.GoalE); ++Try)
		{
			const double A = Dir + F.Rng.Uniform(-1.0, 1.0) * (0.4 + 0.15 * Try);
			const double R = FlyM * F.Rng.Uniform(0.6, 1.6);
			F.GoalN = F.N + R * std::cos(A);
			F.GoalE = F.E + R * std::sin(A);
		}
		std::vector<std::pair<double, size_t>> Order;
		for (size_t K = 0; K < F.Members.size(); ++K)
			Order.push_back({std::hypot(F.Members[K].N - Near->North, F.Members[K].E - Near->East), K});
		std::sort(Order.begin(), Order.end());
		for (size_t R = 0; R < Order.size(); ++R)
		{
			FMember& M = F.Members[Order[R].second];
			M.TakeOffDelay = 0.35 * double(R) / std::max(1.0, std::sqrt(double(Order.size()) / 4.0)) + F.Rng.Uniform(0.0, 0.6);
			M.State = EBirdState::TakingOff;
			M.StateT = 0.0;
			M.Heading = Dir + F.Rng.Uniform(-0.4, 0.4);
		}
		// the flock's track starts where the birds sat
		F.Path.assign(1, {F.N, F.E, 0.0, Dir});
		F.Up = 0.0;
		return true;
	}

	void FBirdFlocks::StepLeader(FFlock& F, double Dt, const FWildlifeConditions& C, const FBirdObservers& Obs, const FWildlifeHabitatMap& Map)
	{
		const FWildBird& B = Table.Birds[size_t(F.Bird)];
		const FBirdStyleParams& P = BirdStyleParams(B.Style);
		const double WindMs = C.WindKn * 0.514444;
		const double WindTo = (C.WindFromDeg + 180.0) * kPi / 180.0;
		const double WN = WindMs * std::cos(WindTo), WE = WindMs * std::sin(WindTo);

		if (F.bResting)
		{
			// rafts drift slowly downwind and turn into the wind; waders stand
			if (B.Style != EBirdStyle::Wading)
			{
				F.N += 0.02 * WN * Dt;
				F.E += 0.02 * WE * Dt;
			}
			F.Heading = WindTo + kPi;
			return;
		}
		// heights are over the water: over land they keep the same height over the ground (the cell here and 100 m on)
		auto GroundUnder = [&](double N, double E, double H)
		{
			return std::max(Map.TopAt(N, E), std::max(Map.TopAt(N + 50.0 * std::cos(H), E + 50.0 * std::sin(H)),
				Map.TopAt(N + 100.0 * std::cos(H), E + 100.0 * std::sin(H))));
		};
		if (F.bCircling)
		{
			// the centre drifts with the wind (a thermal, a bait ball) and wanders toward its goal
			const double ToGoal = std::atan2(F.GoalE - F.E, F.GoalN - F.N);
			F.N += (0.4 * WN + 0.5 * std::cos(ToGoal)) * Dt;
			F.E += (0.4 * WE + 0.5 * std::sin(ToGoal)) * Dt;
			const double Ground = Map.TopAt(F.N, F.E);
			F.Up += (F.TargetUp + Ground - F.Up) * std::min(1.0, 0.2 * Dt);
			return;
		}
		const FBirdObservers::FBoat* Player = PlayerBoat(Obs);
		if (F.bFollowBoat && Player)
		{
			const FBirdObservers::FBoat& Boat = *Player;
			F.GoalN = Boat.North - 35.0 * std::cos(Boat.HeadingRad);
			F.GoalE = Boat.East - 35.0 * std::sin(Boat.HeadingRad);
		}
		const double ToN = F.GoalN - F.N, ToE = F.GoalE - F.E;
		const double ToGoalM = std::hypot(ToN, ToE);
		// steer to the goal at the style's turn rate, with a little wander (insect hunters zigzag)
		const double Want = std::atan2(ToE, ToN) + P.Wander * 1.2 * std::sin(F.Age * (0.7 + 0.13 * double(F.Seed % 7)));
		const double MaxTurn = P.TurnRateDeg * kPi / 180.0 * Dt;
		F.Heading = WrapPi(F.Heading + std::max(-MaxTurn, std::min(MaxTurn, WrapPi(Want - F.Heading))));
		double Speed = P.CruiseMs;
		if (F.bFollowBoat && Player) Speed = std::max(2.0, std::min(P.CruiseMs * 1.3, Player->SpeedMs + 0.05 * ToGoalM));
		if (F.bLanding) Speed *= 0.6;
		// ground track: the air speed along the heading plus most of the wind (gulls into the wind hang)
		const double VN = Speed * std::cos(F.Heading) + 0.6 * WN, VE = Speed * std::sin(F.Heading) + 0.6 * WE;
		F.N += VN * Dt;
		F.E += VE * Dt;
		F.Speed = std::max(0.5, std::hypot(VN, VE));
		double Up = F.TargetUp;
		if (B.Style == EBirdStyle::Shearing) Up = P.AltMinM + (P.AltMaxM - P.AltMinM) * std::fabs(std::sin(0.25 * F.Age + double(F.Seed % 11)));
		if (F.bLanding) Up = 0.0;
		else Up += GroundUnder(F.N, F.E, F.Heading);
		// climb fast enough to clear a bank ahead, ease down slowly
		const double Rate = Up > F.Up ? (F.bFlushed ? 0.6 : 0.8) : 0.3;
		F.Up += (Up - F.Up) * std::min(1.0, Rate * Dt);
		if (!F.bLanding) F.Up = std::max(F.Up, Map.TopAt(F.N, F.E) + 0.5);
		if (ToGoalM < 60.0 && !F.bLanding)
		{
			const bool bCanLand = P.RestShare > 0.0 && !F.bLeaving && !F.bFollowBoat && !F.bPassing && CanRestAt(B, Map, F.N, F.E);
			if (F.bPassing)
			{
				// past her: on along the same line
				F.bPassing = false;
				F.GoalN = F.N + 600.0 * std::cos(F.Heading);
				F.GoalE = F.E + 600.0 * std::sin(F.Heading);
				if (!(Map.BitsAt(F.GoalN, F.GoalE) & B.Habitats)) NewGoal(F, Map, F.Rng.Uniform(800.0, 2500.0));
			}
			else if ((F.bFlushed && CanRestAt(B, Map, F.N, F.E)) || (bCanLand && F.Rng.Uniform01() < 0.3))
			{
				F.bLanding = true;
				for (FMember& M : F.Members)
				{
					M.State = EBirdState::Landing;
					M.StateT = -F.Rng.Uniform(0.0, 3.0);
				}
				F.GoalN = F.N + 60.0 * std::cos(F.Heading);
				F.GoalE = F.E + 60.0 * std::sin(F.Heading);
			}
			else if (!F.bFollowBoat)
			{
				const FBirdStyleParams& PS = P;
				if (!F.bLeaving && PS.CircleShare > 0.0 && F.Rng.Uniform01() < PS.CircleShare)
				{
					F.bCircling = true;
					F.TargetUp = PS.CircleAltM * F.Rng.Uniform(0.7, 1.3);
					for (FMember& M : F.Members)
					{
						M.OffA = PS.CircleRadiusM * F.Rng.Uniform(0.5, 1.5);
						M.OffB = F.Rng.Uniform(0.0, kTwoPi);
						M.OffC = F.Rng.Uniform(-0.2, 0.2) * F.TargetUp;
						M.State = EBirdState::Circling;
					}
				}
				NewGoal(F, Map, F.Rng.Uniform(800.0, 2500.0));
			}
		}
		// the track the followers fly
		F.PathT += Dt;
		while (F.PathT >= kPathStep)
		{
			F.PathT -= kPathStep;
			F.Path.push_back({F.N, F.E, F.Up, F.Heading});
			if (F.Path.size() > kPathPoints) F.Path.erase(F.Path.begin());
		}
	}

	void FBirdFlocks::StepMembers(FFlock& F, double Dt, const FWildlifeHabitatMap& Map)
	{
		const FWildBird& B = Table.Birds[size_t(F.Bird)];
		const FBirdStyleParams& P = BirdStyleParams(B.Style);
		const double Cycle = P.FlapSeconds + P.GlideSeconds;
		const double Span = B.SizeM;
		// Where the track was a given distance behind the leader (the newest point is the leader's last). The arc length to
		// each point back is measured once a flock (PathCum[J]: to the J-th point back, 0 the leader), then each bird finds
		// its segment by bisection: walking the track per bird was most of the update in big flocks.
		const size_t NP = F.Path.size();
		bool bTrack = false;
		for (const FMember& M : F.Members) bTrack |= !F.bResting && !F.bCircling && M.State != EBirdState::OnWater;
		if (bTrack)
		{
			PathCum.resize(NP + 1);
			PathCum[0] = 0.0;
			double PN = F.N, PE = F.E;
			for (size_t J = 0; J < NP; ++J)
			{
				const FPathPoint& Pt = F.Path[NP - 1 - J];
				const double SN = PN - Pt.N, SE = PE - Pt.E;
				PathCum[J + 1] = PathCum[J] + std::sqrt(SN * SN + SE * SE);
				PN = Pt.N; PE = Pt.E;
			}
		}
		auto Back = [&](double Dist, double& N, double& E, double& Up, double& H)
		{
			// the first segment (from the point J-1 back to J) reaching Dist, skipping zero-length ones
			size_t J = size_t(std::lower_bound(PathCum.begin() + 1, PathCum.begin() + std::ptrdiff_t(NP + 1), Dist) - PathCum.begin());
			while (J <= NP && PathCum[J] - PathCum[J - 1] <= 1e-6) ++J;
			if (J <= NP)
			{
				const FPathPoint& Pt = F.Path[NP - J];
				const double PN = J == 1 ? F.N : F.Path[NP - J + 1].N, PE = J == 1 ? F.E : F.Path[NP - J + 1].E;
				const double PU = J == 1 ? F.Up : F.Path[NP - J + 1].Up;
				const double T = (Dist - PathCum[J - 1]) / (PathCum[J] - PathCum[J - 1]);
				N = PN + (Pt.N - PN) * T; E = PE + (Pt.E - PE) * T; Up = PU + (Pt.Up - PU) * T; H = Pt.Heading;
				return;
			}
			// past the track's end: straight on back from its oldest point
			const double Left = Dist - PathCum[NP];
			const double PN = NP ? F.Path[0].N : F.N, PE = NP ? F.Path[0].E : F.E, PU = NP ? F.Path[0].Up : F.Up;
			H = NP ? F.Path[0].Heading : F.Heading;
			N = PN - Left * std::cos(H); E = PE - Left * std::sin(H); Up = PU;
		};
		bool bAllLanded = F.bLanding;
		for (size_t K = 0; K < F.Members.size(); ++K)
		{
			FMember& M = F.Members[K];
			const double OldN = M.N, OldE = M.E, OldH = M.Heading;
			M.StateT += Dt;
			double TN = F.N, TE = F.E, TU = F.Up, TH = F.Heading;   // the member's slot
			if (F.bResting)
			{
				TN = F.N + M.OffA; TE = F.E + M.OffB; TU = 0.0; TH = F.Heading + 0.3 * std::sin(M.OffA);
			}
			else if (F.bCircling)
			{
				const double Dir = F.Side;
				const double W = Dir * P.CruiseMs / std::max(5.0, M.OffA);
				const double A = M.OffB + W * F.Age;
				TN = F.N + M.OffA * std::cos(A);
				TE = F.E + M.OffA * std::sin(A);
				TU = std::max(2.0, F.Up + M.OffC);
				TH = A + Dir * 0.5 * kPi;
			}
			else
			{
				Back(std::max(0.0, M.OffA), TN, TE, TU, TH);
				TN += -M.OffB * std::sin(TH);   // to the right of the track for positive OffB (east of north)
				TE += M.OffB * std::cos(TH);
				TU = std::max(F.bLanding ? 0.0 : 0.6, TU + M.OffC);
			}
			// flying, a slot never takes a bird into the ground or the trees
			if (!F.bResting && !F.bLanding) TU = std::max(TU, Map.TopAt(TN, TE) + 0.6);
			if (Dt <= 0.0)
			{
				// a new flock: every bird starts in its slot
				M.N = TN; M.E = TE; M.Up = F.bResting ? 0.0 : TU; M.Heading = TH;
			}

			if (M.State == EBirdState::TakingOff)
			{
				// sat still until its turn, then a running take-off: away, low, wings hard
				if (M.StateT < M.TakeOffDelay) { bAllLanded = false; continue; }
				const double T = M.StateT - M.TakeOffDelay;
				const double V = P.CruiseMs * Smooth(0.0, 2.5, T);
				M.N += V * std::cos(M.Heading) * Dt;
				M.E += V * std::sin(M.Heading) * Dt;
				M.Up += std::min(2.0, 0.8 * T) * Dt;
				const double Join = Smooth(1.5, 4.0, T);
				M.N += (TN - M.N) * std::min(1.0, Join * 1.5 * Dt);
				M.E += (TE - M.E) * std::min(1.0, Join * 1.5 * Dt);
				M.Up += (TU - M.Up) * std::min(1.0, Join * 1.0 * Dt);
				M.Heading = WrapPi(M.Heading + WrapPi(std::atan2(M.E - OldE, M.N - OldN) - M.Heading) * std::min(1.0, 3.0 * Dt));
				if (T > 4.0) M.State = EBirdState::Flying;
				M.Phase = std::fmod(M.Phase + P.BeatHz * 1.3 * Dt, 1.0);
				M.CycleT = 0.0;
				bAllLanded = false;
				continue;
			}
			if (M.State == EBirdState::Landing)
			{
				// in turn, glide down, a few beats to stop, wings folded on the water
				const double T = M.StateT;
				const double Close = Smooth(0.0, 3.0, T);
				M.N += (TN - M.N) * std::min(1.0, 2.0 * Dt) * (1.0 - Close) + std::cos(M.Heading) * P.CruiseMs * (1.0 - Close) * 0.4 * Dt;
				M.E += (TE - M.E) * std::min(1.0, 2.0 * Dt) * (1.0 - Close) + std::sin(M.Heading) * P.CruiseMs * (1.0 - Close) * 0.4 * Dt;
				M.Up = std::max(0.0, M.Up - std::max(0.5, M.Up) * Smooth(0.0, 1.0, T) * Dt);
				M.Phase = std::fmod(M.Phase + P.BeatHz * Dt, 1.0);
				if (T > 3.0 && M.Up <= 0.05)
				{
					M.Up = 0.0;
					M.State = B.Style == EBirdStyle::Wading ? EBirdState::Standing : EBirdState::OnWater;
					NewSplashes.push_back({M.N, M.E, float(Span), false});
				}
				else bAllLanded = false;
				continue;
			}
			if (M.State == EBirdState::OnWater || M.State == EBirdState::Standing)
			{
				if (F.bResting)
				{
					M.N += (TN - M.N) * std::min(1.0, 0.2 * Dt);
					M.E += (TE - M.E) * std::min(1.0, 0.2 * Dt);
					M.Heading = WrapPi(M.Heading + WrapPi(TH - M.Heading) * std::min(1.0, 0.3 * Dt));
					M.Up = 0.0;
				}
				continue;
			}
			bAllLanded = false;

			if (M.State == EBirdState::Diving)
			{
				// fold and drop
				const double T = M.StateT;
				M.Up = std::max(0.0, M.DiveFromUp * (1.0 - T * T / 0.8));
				M.Pitch = -1.2;
				if (M.Up <= 0.0)
				{
					NewSplashes.push_back({M.N, M.E, float(Span), true});
					M.State = EBirdState::OnWater;
					M.StateT = 0.0;
					M.Pitch = 0.0;
				}
				continue;
			}
			if (M.State == EBirdState::OnWater && !F.bResting)
			{
				continue;
			}
			// a plunging bird surfaces and climbs back to its circle
			if (F.bCircling && B.Style == EBirdStyle::HoverPlunge && M.State == EBirdState::Circling && M.Up > 4.0 &&
				F.Rng.Uniform01() < Dt / 25.0)
			{
				M.State = EBirdState::Diving;
				M.StateT = 0.0;
				M.DiveFromUp = M.Up;
				continue;
			}

			// fly to the slot: close in quickly, follow tightly once there
			const double GN = TN - M.N, GE = TE - M.E;
			const double Gap = std::sqrt(GN * GN + GE * GE);
			const double Rate = Gap > 5.0 ? 1.2 : 6.0;
			M.N += (TN - M.N) * std::min(1.0, Rate * Dt);
			M.E += (TE - M.E) * std::min(1.0, Rate * Dt);
			M.Up += (TU - M.Up) * std::min(1.0, 2.0 * Dt);
			if (Dt > 0.0)
			{
				const double MN = M.N - OldN, ME = M.E - OldE;
				const double Moved = std::sqrt(MN * MN + ME * ME);
				M.Heading = Moved > 0.01 ? std::atan2(M.E - OldE, M.N - OldN) : TH;
			}
			else M.N = TN, M.E = TE, M.Up = TU, M.Heading = TH;
			// bank into the turn
			const double YawRate = Dt > 0.0 ? WrapPi(M.Heading - OldH) / Dt : 0.0;
			const double Bank = std::atan(F.Speed * YawRate / kG);
			M.Bank += (std::max(-0.9, std::min(0.9, Bank)) - M.Bank) * std::min(1.0, 4.0 * Dt);
			if (B.Style == EBirdStyle::Shearing) M.Bank = 0.8 * std::sin(0.25 * F.Age + double(F.Seed % 11) + 0.3 * double(K));
			M.Pitch = 0.0;
			// a burst of beats, then a glide
			M.CycleT = Cycle > 0.0 ? std::fmod(M.CycleT + Dt, Cycle) : 0.0;
			const bool bFlap = P.GlideSeconds <= 0.0 || M.CycleT < P.FlapSeconds;
			M.State = F.bCircling ? EBirdState::Circling : (bFlap ? EBirdState::Flying : EBirdState::Gliding);
			if (bFlap) M.Phase = std::fmod(M.Phase + P.BeatHz * Dt, 1.0);
			// and never through a bank it is climbing over
			if (!F.bLanding) M.Up = std::max(M.Up, Map.TopAt(M.N, M.E) + 0.4);
		}
		// Plunged birds rest a moment, then climb back.
		for (FMember& M : F.Members)
		{
			if (M.State == EBirdState::OnWater && !F.bResting && !F.bLanding && M.StateT > 1.5)
			{
				M.State = EBirdState::TakingOff;
				M.StateT = 0.0;
				M.TakeOffDelay = 0.0;
			}
		}
		if (F.bLanding && bAllLanded && !F.Members.empty())
		{
			F.bLanding = false;
			F.bFlushed = false;
			F.bResting = true;
			F.Up = 0.0;
			double SN = 0.0, SE = 0.0;
			for (const FMember& M : F.Members) { SN += M.N; SE += M.E; }
			F.N = SN / double(F.Members.size());
			F.E = SE / double(F.Members.size());
			for (FMember& M : F.Members) { M.OffA = M.N - F.N; M.OffB = M.E - F.E; }
		}
	}

	void FBirdFlocks::StepFlock(FFlock& F, double Dt, const FWildlifeConditions& C, const FBirdObservers& Obs, const FWildlifeHabitatMap& Map)
	{
		const FWildBird& B = Table.Birds[size_t(F.Bird)];
		F.Age += Dt;
		F.Life -= Dt;
		const double CamD = std::hypot(F.N - Obs.CamNorth, F.E - Obs.CamEast);
		if (F.bLeaving)
		{
			F.Fade = std::max(0.0, F.Fade - Dt / kFadeSeconds * (CamD > 0.9 * FarM ? 1.0 : 0.0));
		}
		else
		{
			F.Fade = std::min(1.0, F.Fade + Dt / kFadeSeconds);
		}
		CheckFlush(F, Obs, Map);
		// a raft a boat is sailing at waits for her (it lifts as she arrives, a flush, not just before)
		if (F.Life <= 0.0 && !F.bLeaving && F.bResting && !F.bFlushed && BoatClosingOn(F, Obs)) F.Life = kWaitSeconds;
		if (F.Life <= 0.0 && !F.bLeaving)
		{
			// time to go: rafts take off, circlers break off, everyone heads out of the camera's 2 km
			EndStay(F);
			F.bLeaving = true;
			F.bFollowBoat = false;
			if (F.bResting && !F.bFlushed)
			{
				// they take off on their own, into the wind they face
				FBirdObservers Self;
				FBirdObservers::FBoat From;
				From.North = F.N - 10.0 * std::cos(F.Heading);
				From.East = F.E - 10.0 * std::sin(F.Heading);
				From.HeadingRad = F.Heading;
				Self.Boats.push_back(From);
				if (CheckFlush(F, Self, Map, true)) --St.Flushes;   // not a boat's doing
			}
			F.bCircling = false;
			const double Out = std::atan2(F.E - Obs.CamEast, F.N - Obs.CamNorth);
			F.GoalN = Obs.CamNorth + (FarM + 800.0) * std::cos(Out);
			F.GoalE = Obs.CamEast + (FarM + 800.0) * std::sin(Out);
			F.bLanding = false;
			for (FMember& M : F.Members) if (M.State == EBirdState::Circling) M.State = EBirdState::Flying;
		}
		// Gulls and terns now and then follow the player's boat for a while.
		const FBirdObservers::FBoat* Player = PlayerBoat(Obs);
		if (!F.bLeaving && !F.bResting && !F.bCircling && !F.bFollowBoat && !F.bLanding && B.Style == EBirdStyle::FlapHang && Player &&
			std::hypot(F.N - Player->North, F.E - Player->East) < 300.0 && F.Rng.Uniform01() < Dt / 600.0)
		{
			F.bFollowBoat = true;
			F.Life = std::max(F.Life, 120.0);
		}
		if (F.bFollowBoat && (F.Life < 30.0 || !Player)) F.bFollowBoat = false;
		StepLeader(F, Dt, C, Obs, Map);
		// Most birds in the 2 km band are past the drawing budget: a flock with none drawn last frame steps its birds every
		// fourth frame (on the time gone since), a drawn one every frame.
		F.MemberDt += Dt;
		if (F.bDrawn || F.bLanding || ((Frame + F.Seed) & 3u) == 0)
		{
			StepMembers(F, F.MemberDt, Map);
			F.MemberDt = 0.0;
		}
	}

	void FBirdFlocks::BuildDraw(const FBirdObservers& Obs)
	{
		Drawn.clear();
		St.Flocks = int(Flocks.size());
		St.Birds = St.Airborne = St.Resting = 0;
		std::vector<FBirdDraw>& All = Candidates;
		All.clear();
		CandidateFlock.clear();
		for (size_t FI = 0; FI < Flocks.size(); ++FI)
		{
			FFlock& F = Flocks[FI];
			F.bDrawn = false;
			const FWildBird& B = Table.Birds[size_t(F.Bird)];
			const FBirdStyleParams& P = BirdStyleParams(B.Style);
			for (const FMember& M : F.Members)
			{
				++St.Birds;
				const bool bDown = M.State == EBirdState::OnWater || M.State == EBirdState::Standing ||
					(M.State == EBirdState::TakingOff && M.StateT < M.TakeOffDelay);
				bDown ? ++St.Resting : ++St.Airborne;
				const double DN = M.N - Obs.CamNorth, DE = M.E - Obs.CamEast, DU = M.Up - Obs.CamUp;
				const double Dist = std::sqrt(DN * DN + DE * DE + DU * DU);
				if (Dist > FarM || F.Fade <= 0.0) continue;
				FBirdDraw D;
				D.North = M.N; D.East = M.E; D.Up = M.Up;
				D.HeadingRad = float(M.Heading);
				D.PitchRad = float(M.Pitch);
				D.BankRad = float(M.Bank);
				D.WingPhase = float(M.Phase);
				const bool bBeat = M.State == EBirdState::Flying || M.State == EBirdState::TakingOff ||
					M.State == EBirdState::Landing || (M.State == EBirdState::Circling && (P.GlideSeconds <= 0.0 ||
					std::fmod(M.CycleT, std::max(0.01, P.FlapSeconds + P.GlideSeconds)) < P.FlapSeconds));
				D.WingAmp = bDown ? 0.0f : (bBeat ? 1.0f : 0.0f);
				D.Fold = (bDown || M.State == EBirdState::Diving) ? 1.0f : 0.0f;
				D.Fade = float(F.Fade);
				D.SizeM = float(B.SizeM * M.Scale);
				D.Bird = uint16_t(F.Bird);
				D.Style = B.Style;
				D.State = bDown ? (B.Style == EBirdStyle::Wading ? EBirdState::Standing : EBirdState::OnWater) : M.State;
				D.DistanceM = float(Dist);
				D.bInView = !Obs.bHasView || Dist < 1e-3 ||
					(DN * Obs.ViewNorth + DE * Obs.ViewEast + DU * Obs.ViewUp) >= Obs.ViewCosHalf * Dist;
				All.push_back(D);
				CandidateFlock.push_back(uint32_t(FI));
			}
		}
		// In view first, then nearest first: out of view a bird ranks as if ViewOutsideWeight times farther (it still gets
		// drawn when there is budget to spare, so turning the camera finds birds already there).
		DrawRank.clear();
		DrawRank.reserve(All.size());
		for (size_t K = 0; K < All.size(); ++K)
			DrawRank.push_back({All[K].DistanceM * (All[K].bInView ? 1.0f : float(ViewOutsideWeight)), uint32_t(K)});
		std::sort(DrawRank.begin(), DrawRank.end());
		// Bodies to the nearest within the near and mid budgets (a near bird past Near takes a mid body); every other bird a
		// quad within Far, so a big flock close by is drawn whole rather than cut at the bodies' budget.
		int NNear = 0, NMid = 0, NFar = 0, NView = 0;
		for (const std::pair<float, uint32_t>& R : DrawRank)
		{
			FBirdDraw& D = All[R.second];
			if (D.DistanceM < NearM && NNear < Budget.Near) { D.bBody = true; ++NNear; }
			else if (D.DistanceM < MidM && NMid < Budget.Mid) { D.bBody = true; ++NMid; }
			else if (NFar < Budget.Far) { D.bBody = false; ++NFar; }
			else continue;
			NView += D.bInView ? 1 : 0;
			Flocks[CandidateFlock[R.second]].bDrawn = true;
			Drawn.push_back(D);
		}
		St.Near = NNear; St.Mid = NMid; St.Far = NFar; St.InView = NView;
	}
}
