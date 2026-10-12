#pragma once

#include "SailingPhysicsApi.h"
#include <string>
#include <vector>

namespace Sailing
{
	/**
	 * A navigation light's character as the chart gives it (S-57 LITCHR, SIGGRP, SIGPER, COLOUR, VALNMR), turned into
	 * the on/off rhythm you see on the water and the label the NOAA chart prints ("Fl(2) G 6s 4M").
	 *
	 * Timing follows U.S. aids-to-navigation practice: a flash lasts 0.4 s with 0.6 s between flashes in a group;
	 * long flash 2 s; quick 60 per minute (0.3 s on), very quick 120 (0.2 s on), ultra quick 240 (0.1 s on);
	 * isophase half on, half off; occulting dark 25% of the period (groups of 0.6 s eclipses 0.6 s apart);
	 * Morse code dot 0.4 s, dash 1.2 s, 0.4 s between them.
	 */
	struct SAILINGPHYSICS_API FLightCharacter
	{
		int Litchr = 1;               // S-57 LITCHR: 1 F, 2 Fl, 3 LFl, 4 Q, 5 VQ, 6 UQ, 7 Iso, 8 Oc, 9 IQ, 10 IVQ, 11 IUQ, 12 Mo, ...
		std::vector<int> Groups;      // from SIGGRP "(2)" -> {2}; "(2+1)" -> {2, 1}; "(A)" -> Morse letter
		std::string Morse;            // Morse letter for Mo
		double Period = 0.0;          // SIGPER, s (0 = continuous rhythm)
		std::vector<int> Colours;     // S-57 colour codes: 1 white, 3 red, 4 green, 6 yellow, ...
		double RangeNm = 0.0;         // VALNMR, nominal range
		double HeightM = 0.0;         // HEIGHT above MHW

		/** Parses SIGGRP ("(2)", "(2+1)", "(A)", "()" or empty). */
		void SetGroup(const std::string& SigGrp);
		/** Whether the light shows at time t (s) into its cycle (any phase offset is the caller's). */
		bool IsOn(double Time) const;
		/** The chart label, e.g. "Fl G 2.5s 4M", "Q R", "Iso W 6s", "Mo(A) W 8s". */
		std::string Label() const;
		/** The cycle length actually used (the period, or the rhythm's own length when no period is charted). */
		double CycleLength() const;
	};

	/** Chart abbreviation of an S-57 colour code ("W", "R", "G", "Y", ...). */
	SAILINGPHYSICS_API const char* ColourAbbreviation(int Colour);
}
