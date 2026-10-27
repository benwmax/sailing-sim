#pragma once

#include "SailingPhysicsApi.h"
#include "BoatModel.h"
#include "Ocean.h"
#include "Waves.h"
#include "Weather.h"
#include "Wind.h"
#include <memory>

namespace Sailing
{
	/**
	 * Sea trials for the wave physics (docs/wave-physics/): a boat sailed in a given wind and sea, measured the way the
	 * tests and scripts/polar.sh --sea read it. Plain C++ so the standalone tools and the automation tests share it.
	 */
	struct SAILINGPHYSICS_API FTrialSeaSpec
	{
		double WindKnots = 15.0;
		double WindFromDeg = 0.0;      // map frame; the boat's heading is set from it and the TWA
		double GustIntensity = 0.0;    // FWindParams::GustIntensity (0 = steady)
		uint32_t Seed = 1;
		// The wind's own chop (FWaveField) on this fetch; bCalibrationSea is the polar's sea (FWaveParams).
		double FetchMeters = 5000.0;
		bool bCalibrationSea = false;
		// An open-sea FFT spectrum under the chop (FOcean), as the Gulf has.
		bool bOcean = false;
		FOceanParams Ocean;
		// The prologue's gale instead (step 4): the mistral preset driving the wind every quarter second and its sea (the
		// fetch-limited wind sea and the older sea with it, FFT, plus the chop on a 200 m fetch), scaled to WindKnots,
		// blowing from WindFromDeg (the scene's stand-in direction), at GaleHour. bGaleSea = false: the gale's wind on flat
		// water.
		bool bGale = false;
		bool bGaleSea = true;
		double GaleHour = 17.5;

		/** The prologue gale (Content/Prologue/prologue.json: 32 kn on the Gulf stand-in from 180 deg at 17.5 h). */
		static FTrialSeaSpec Gale(uint32_t Seed, double Knots = 32.0, bool bSea = true);
	};

	/** The wind and sea of a trial, stepped on the trial's clock. */
	class SAILINGPHYSICS_API FTrialSea
	{
	public:
		explicit FTrialSea(const FTrialSeaSpec& Spec);
		/** Advances the weather (the gale re-evaluates every quarter second around the boat) and the sea's growth. */
		void Update(double T, double BoatX, double BoatY);
		const FWindField& GetWind() const { return Wind; }
		const FWaveField* GetWaves() const { return bWaves ? &Waves : nullptr; }
		double WindFromDeg() const { return FromDeg; }
		/** Heading (rad, map frame) that puts the true wind at Twa degrees (positive: from starboard). */
		double HeadingFor(double TwaDeg) const { return (FromDeg - TwaDeg) * kDegToRad; }

	private:
		FTrialSeaSpec Spec;
		FWeatherSystem Weather;
		FWindField Wind;
		FWaveField Waves;
		std::shared_ptr<FOcean> Ocean;
		double Scale = 1.0, NextWeather = 0.0, FromDeg = 0.0;
		bool bWaves = true;
	};

	struct FSeaRunResult
	{
		double MeanKnots = 0.0;
		double NetKnots = 0.0;     // straight-line distance made good over the measured time (drift, if she is not sailing)
		double MinKnots = 0.0, MaxKnots = 0.0;   // of one-second means (a GPS's)
		double MeanCalmN = 0.0;    // hulls' calm-water resistance
		double MeanWaveN = 0.0;    // added resistance in the waves
		double MeanSurgeN = 0.0;   // the waves' slope push along the bow (averages near zero unless she rides them)
		// Forward acceleration (m/s^2) while the waves' push along her course (FBoatTelemetry::WaveSlopeSurge over her
		// weight: the slope her hull feels) is downhill by more than FaceSlope (on a face) and uphill by as much (on a
		// back), and the share of the time on faces.
		double FaceAccel = 0.0, BackAccel = 0.0, FaceShare = 0.0;
		// docs/surfing/: speed by the wave's phase under her, from the same slope (bins: steep back under -2 FaceSlope, back,
		// level, face, steep face over 2 FaceSlope), the share of the time in each; the share of one-second means over
		// 1.5 x her hull speed (1.34 sqrt(LWL in ft) kn), and her mean course error (|TWA - the autopilot's|, deg) on
		// faces and on backs (a broach starts on a face).
		double PhaseKnots[5] = {}, PhaseShare[5] = {};
		double SurfShare = 0.0, HullSpeedKnots = 0.0;
		double FaceCourseErrDeg = 0.0, BackCourseErrDeg = 0.0;
		double MeanHeelDeg = 0.0, MaxTiltDeg = 0.0;
		double MeanTwaDeg = 0.0;
		double Hs = 0.0;           // significant height where she sailed
		bool bCapsized = false;
	};

	/**
	 * Sails Config at TwaDeg (signed: + = wind from starboard) in the trial sea, trimmed and steered by the polar's crew
	 * (FAutoTrim, FAutopilot), settles for Settle seconds and measures the next Seconds.
	 */
	SAILINGPHYSICS_API FSeaRunResult RunInSea(const FBoatConfig& Config, const FTrialSeaSpec& Sea, double TwaDeg, int Reefs, bool bSpinnaker,
		double Settle, double Seconds, double FaceSlope = 0.02);

	/**
	 * The prologue's tack in the gale (step 4's ready-about), the way SailingSim.Prologue.Gale sails it: close-hauled on
	 * starboard with the crew at the stations (FStationControls), then at 60 + 7 x Seed s the helm calls the tack, takes
	 * the wheel and steers hard (autopilot at 0.6 of the wheel, short of an over-stall) for TWA -45, timing it on the waves
	 * (FAutopilot::bTimeTacks; the main held in from the call: FStationControls::CallTack). Returns the seconds from the call until
	 * she has held port tack (TWA -30 to -100) for one second, or -1 if she has not within 90 s. Config as the scene sets
	 * it (FSceneLimits applied by the caller).
	 */
	SAILINGPHYSICS_API double RunGaleTack(const FBoatConfig& Config, int Reefs, uint32_t Seed, bool bSea, double Knots = 32.0);

	/** RunGaleTack's tack in detail: its seconds, her mean speed over the 20 s before the call and her slowest through it (kn). */
	struct FGaleTackResult
	{
		double Seconds = -1.0;
		double SpeedBeforeKnots = 0.0;
		double MinSpeedKnots = 0.0;
	};
	/**
	 * docs/trimmer-hands/: how the crew's hands (FAutoTrim) work the sheets: a boat sailed by the autopilot at a true wind
	 * angle in a wind (GustIntensity: FWindParams'; FetchMeters of lake chop, 1 for flat water) for Seconds after a minute's
	 * settling. Travel is the summed movement of each control per minute, in its whole travels (the traveller's is 2).
	 */
	struct FTrimHandsResult
	{
		double MainTravelPerMin = 0.0, TravelerTravelPerMin = 0.0, JibTravelPerMin = 0.0;
		double AdjustmentsPerMin = 0.0;
		double MeanKnots = 0.0;
	};
	SAILINGPHYSICS_API FTrimHandsResult MeasureTrimHands(const FBoatConfig& Config, double TrueWindKnots, double TwaDeg, double FetchMeters,
		double GustIntensity, double Seconds, bool bHands = true);

	SAILINGPHYSICS_API FGaleTackResult RunGaleTackDetail(const FBoatConfig& Config, int Reefs, uint32_t Seed, bool bSea, double Knots = 32.0);
}
